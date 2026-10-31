"""Data aggregation & storage: fetch from every provider, standardize, and upsert into PostgreSQL.

Jobs (wired to APScheduler in app/services/scheduler.py):
* backfill        - first start only: loads BACKFILL_DAYS of history + 7 days of hourly metrics
* daily sync      - re-fetches the last SYNC_LOOKBACK_DAYS of costs + refreshes inventory
* intraday costs  - refreshes today's running cost (near-real-time view)
* metrics         - pulls the latest utilization samples every METRICS_INTERVAL_MINUTES

All writes are idempotent upserts keyed on natural keys, so re-running any job is safe.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import CostRecord, Resource, ResourceMetric, SyncRun
from app.services.providers import get_providers
from app.services.providers.base import CostItem, MetricItem, ProviderNotConfigured, ResourceItem

log = logging.getLogger("cloudlens.ingestion")
CHUNK = 1000


def _insert(db: Session, model):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(model)


def _chunks(rows: List[dict], size: int = CHUNK) -> Iterable[List[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def local_today() -> date:
    return datetime.now(ZoneInfo(get_settings().TIMEZONE)).date()


# ---------------------------------------------------------------- upserts
def upsert_costs(db: Session, items: List[CostItem], source: str) -> int:
    if not items:
        return 0
    now = datetime.now(timezone.utc)
    # collapse duplicates on the natural key before inserting (ON CONFLICT can't touch a row twice)
    merged: Dict[tuple, dict] = {}
    for it in items:
        key = (it.provider, it.account_id, it.usage_date, it.service, it.environment, it.region, it.resource_id or "")
        if key in merged:
            merged[key]["cost_usd"] += it.cost_usd
            merged[key]["cost_original"] += it.cost_original
            merged[key]["usage_quantity"] += it.usage_quantity
            continue
        merged[key] = dict(
            provider=it.provider, account_id=it.account_id, usage_date=it.usage_date, service=it.service[:120],
            resource_type=it.resource_type, environment=it.environment, region=it.region, resource_id=it.resource_id or "",
            cost_usd=it.cost_usd, cost_original=it.cost_original, currency_original=it.currency_original,
            usage_quantity=it.usage_quantity, usage_unit=it.usage_unit, source=source, ingested_at=now,
        )
    rows = list(merged.values())
    for chunk in _chunks(rows):
        stmt = _insert(db, CostRecord).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "account_id", "usage_date", "service", "environment", "region", "resource_id"],
            set_={
                "cost_usd": stmt.excluded.cost_usd,
                "cost_original": stmt.excluded.cost_original,
                "currency_original": stmt.excluded.currency_original,
                "usage_quantity": stmt.excluded.usage_quantity,
                "resource_type": stmt.excluded.resource_type,
                "source": stmt.excluded.source,
                "ingested_at": stmt.excluded.ingested_at,
            },
        )
        db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_resources(db: Session, items: List[ResourceItem]) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    if items:
        rows = [
            dict(
                provider=r.provider, account_id=r.account_id, resource_id=r.resource_id, name=r.name[:160],
                resource_type=r.resource_type, service=r.service[:120], environment=r.environment, region=r.region,
                sku=(r.sku or "")[:80], status=r.status[:20], tags=r.tags, first_seen_at=now, last_seen_at=now,
            )
            for r in {(x.provider, x.resource_id): x for x in items}.values()
        ]
        for chunk in _chunks(rows):
            stmt = _insert(db, Resource).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["provider", "resource_id"],
                set_={k: getattr(stmt.excluded, k) for k in ("name", "resource_type", "service", "environment", "region", "sku", "status", "tags", "last_seen_at")},
            )
            db.execute(stmt)
        db.commit()
    return {rid: pk for pk, rid in db.execute(select(Resource.id, Resource.resource_id)).all()}


def upsert_metrics(db: Session, items: List[MetricItem], pk_map: Dict[str, int]) -> int:
    rows = [
        dict(
            resource_pk=pk_map[m.resource_id], ts=m.ts, cpu_percent=m.cpu_percent, memory_percent=m.memory_percent,
            storage_percent=m.storage_percent, network_in_mb=m.network_in_mb, network_out_mb=m.network_out_mb,
        )
        for m in items
        if m.resource_id in pk_map
    ]
    if not rows:
        return 0
    uniq = {(r["resource_pk"], r["ts"]): r for r in rows}
    rows = list(uniq.values())
    for chunk in _chunks(rows):
        stmt = _insert(db, ResourceMetric).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["resource_pk", "ts"],
            set_={k: getattr(stmt.excluded, k) for k in ("cpu_percent", "memory_percent", "storage_percent", "network_in_mb", "network_out_mb")},
        )
        db.execute(stmt)
    db.commit()
    return len(rows)


# ---------------------------------------------------------------- jobs
def _start_run(db: Session, provider: str, job: str, triggered_by: str) -> SyncRun:
    run = SyncRun(provider=provider, job=job, data_source=get_settings().DATA_SOURCE, triggered_by=triggered_by, status="running")
    db.add(run)
    db.commit()
    return run


def _finish(db: Session, run: SyncRun, status: str, error: str = "") -> None:
    run.status = status
    run.error = error[:2000]
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def sync_provider(
    db: Session,
    name: str,
    provider,
    job: str,
    cost_start: Optional[date],
    cost_end: Optional[date],
    metrics_hours: float = 0,
    metrics_step: int = 60,
    triggered_by: str = "scheduler",
) -> SyncRun:
    run = _start_run(db, name, job, triggered_by)
    source = get_settings().DATA_SOURCE
    try:
        if not provider.is_configured():
            raise ProviderNotConfigured(f"{name} credentials are not configured")
        if cost_start and cost_end:
            run.cost_records = upsert_costs(db, provider.fetch_costs(cost_start, cost_end), source)
        if metrics_hours:
            resources = provider.fetch_resources()
            pk_map = upsert_resources(db, resources)
            run.resources = len(resources)
            end = datetime.now(timezone.utc)
            start = end - timedelta(hours=metrics_hours)
            run.metric_samples = upsert_metrics(db, provider.fetch_metrics(resources, start, end, step_minutes=metrics_step), pk_map)
        run.api_calls = provider.api_calls
        _finish(db, run, "success")
        log.info("sync %s/%s ok: %s costs, %s resources, %s samples", name, job, run.cost_records, run.resources, run.metric_samples)
    except ProviderNotConfigured as exc:
        db.rollback()
        run.api_calls = provider.api_calls
        _finish(db, run, "skipped", str(exc))
        log.warning("sync %s/%s skipped: %s", name, job, exc)
    except Exception as exc:  # keep other providers running
        db.rollback()
        run.api_calls = provider.api_calls
        _finish(db, run, "failed", f"{type(exc).__name__}: {exc}")
        log.exception("sync %s/%s failed", name, job)
    return run


def run_job(db: Session, job: str, triggered_by: str = "scheduler", providers: Optional[List[str]] = None) -> List[SyncRun]:
    s = get_settings()
    today = local_today()
    plans = {
        "backfill": dict(cost_start=today - timedelta(days=s.BACKFILL_DAYS), cost_end=today + timedelta(days=1), metrics_hours=24 * 7, metrics_step=60),
        "daily": dict(cost_start=today - timedelta(days=s.SYNC_LOOKBACK_DAYS), cost_end=today + timedelta(days=1), metrics_hours=26, metrics_step=60),
        "intraday": dict(cost_start=today, cost_end=today + timedelta(days=1), metrics_hours=0),
        "metrics": dict(cost_start=None, cost_end=None, metrics_hours=max(0.25, s.METRICS_INTERVAL_MINUTES / 60 * 2), metrics_step=s.METRICS_INTERVAL_MINUTES),
        "manual": dict(cost_start=today - timedelta(days=s.SYNC_LOOKBACK_DAYS), cost_end=today + timedelta(days=1), metrics_hours=2, metrics_step=s.METRICS_INTERVAL_MINUTES),
    }
    plan = plans[job]
    runs = []
    for name, provider in get_providers(db).items():
        if providers and name not in providers:
            continue
        runs.append(sync_provider(db, name, provider, job=job, triggered_by=triggered_by, **plan))
    return runs


def backfill_if_empty(db: Session) -> bool:
    count = db.scalar(select(func.count()).select_from(CostRecord))
    if count:
        extend_history(db)
        return False
    log.info("empty database - running initial backfill of %s days", get_settings().BACKFILL_DAYS)
    run_job(db, "backfill", triggered_by="startup")
    return True


def extend_history(db: Session) -> List[SyncRun]:
    """If BACKFILL_DAYS was raised after the first start, fetch the older days that are missing.

    Runs once at startup; costs only one provider call per provider and only when there is a gap.
    """
    s = get_settings()
    target = local_today() - timedelta(days=s.BACKFILL_DAYS)
    runs = []
    for name, provider in get_providers(db).items():
        earliest = db.scalar(select(func.min(CostRecord.usage_date)).where(CostRecord.provider == name))
        if earliest is None or earliest <= target + timedelta(days=1):
            continue
        log.info("extending %s history from %s back to %s", name, earliest, target)
        runs.append(sync_provider(db, name, provider, job="backfill", cost_start=target, cost_end=earliest, triggered_by="startup"))
    return runs


def apply_retention(db: Session) -> Dict[str, int]:
    """Cost optimization: keep storage small by dropping old raw samples and cost lines."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    m = db.query(ResourceMetric).filter(ResourceMetric.ts < now - timedelta(days=s.METRICS_RETENTION_DAYS)).delete(synchronize_session=False)
    c = db.query(CostRecord).filter(CostRecord.usage_date < local_today() - timedelta(days=s.COST_RETENTION_DAYS)).delete(synchronize_session=False)
    r = db.query(SyncRun).filter(SyncRun.started_at < now - timedelta(days=60)).delete(synchronize_session=False)
    db.commit()
    return {"metrics_deleted": m, "costs_deleted": c, "sync_runs_deleted": r}
