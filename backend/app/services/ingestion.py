"""Data aggregation & storage: fetch from every provider, standardize, and upsert into PostgreSQL.

Jobs (wired to APScheduler in app/services/scheduler.py):
* backfill        - first start only: loads BACKFILL_DAYS of history + 7 days of hourly metrics
* daily sync      - re-fetches the last SYNC_LOOKBACK_DAYS of costs + refreshes inventory
* intraday costs  - refreshes today's running cost (near-real-time view)
* metrics         - pulls the latest utilization samples every METRICS_INTERVAL_MINUTES
* load_active     - after a cloud's mode changes: first load, or fills the days missed in that mode

All writes are idempotent upserts keyed on natural keys, so re-running any job is safe.
Each row records its source (mock | live); both are kept, and analytics reads the cloud's selected one.
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
from app.services.providers import connectors_for, get_connectors
from app.services.providers.base import CostItem, MetricItem, ProviderNotConfigured, ResourceItem

log = logging.getLogger("cloudlens.ingestion")
CHUNK = 1000
# AWS bills every Cost Explorer request, so Live connections refresh today's cost less often than the job runs
LIVE_COST_REFRESH_MINUTES = 360


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


def upsert_resources(db: Session, items: List[ResourceItem], source: str) -> Dict[str, int]:
    now = datetime.now(timezone.utc)
    if items:
        rows = [
            dict(
                provider=r.provider, account_id=r.account_id, resource_id=r.resource_id, name=r.name[:160],
                resource_type=r.resource_type, service=r.service[:120], environment=r.environment, region=r.region,
                sku=(r.sku or "")[:80], status=r.status[:20], source=source, tags=r.tags, first_seen_at=now, last_seen_at=now,
            )
            for r in {(x.provider, x.resource_id): x for x in items}.values()
        ]
        for chunk in _chunks(rows):
            stmt = _insert(db, Resource).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["provider", "resource_id"],
                set_={k: getattr(stmt.excluded, k) for k in ("name", "resource_type", "service", "environment", "region", "sku", "status", "source", "tags", "last_seen_at")},
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
def _start_run(db: Session, name: str, provider, job: str, triggered_by: str) -> SyncRun:
    run = SyncRun(provider=name, job=job, data_source=provider.source, environment=provider.environment, triggered_by=triggered_by, status="running")
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
    source = provider.source
    run = _start_run(db, name, provider, job, triggered_by)
    try:
        if not provider.is_configured():
            raise ProviderNotConfigured(f"{name} credentials are not configured")
        if cost_start and cost_end:
            run.cost_records = upsert_costs(db, provider.fetch_costs(cost_start, cost_end), source)
        if metrics_hours:
            resources = provider.fetch_resources()
            pk_map = upsert_resources(db, resources, source)
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


def _ran_recently(db: Session, name: str, environment: str, job: str, minutes: int) -> bool:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return db.scalar(
        select(func.count()).select_from(SyncRun).where(
            SyncRun.provider == name, SyncRun.environment == environment, SyncRun.job == job, SyncRun.data_source == "live", SyncRun.started_at >= since,
        )
    ) > 0


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
    for name, provider in get_connectors(db):
        if providers and name not in providers:
            continue
        if job == "intraday" and provider.source == "live" and _ran_recently(db, name, provider.environment, job, LIVE_COST_REFRESH_MINUTES):
            continue
        runs.append(sync_provider(db, name, provider, job=job, triggered_by=triggered_by, **plan))
    return runs


def _cost_date(db: Session, fn, name: str, provider) -> Optional[date]:
    """Earliest or latest day this connector has data for (a Live connection covers one environment)."""
    conds = [CostRecord.provider == name, CostRecord.source == provider.source]
    if provider.environment:
        conds.append(CostRecord.environment == provider.environment)
    return db.scalar(select(fn(CostRecord.usage_date)).where(*conds))


def backfill_if_empty(db: Session) -> bool:
    empty = [(name, p) for name, p in get_connectors(db) if _cost_date(db, func.max, name, p) is None]
    extend_history(db)
    if not empty:
        return False
    s = get_settings()
    log.info("no data yet for %s - running initial backfill of %s days", ",".join(name for name, _ in empty), s.BACKFILL_DAYS)
    today = local_today()
    for name, p in empty:
        sync_provider(db, name, p, job="backfill", cost_start=today - timedelta(days=s.BACKFILL_DAYS), cost_end=today + timedelta(days=1), metrics_hours=24 * 7, metrics_step=60, triggered_by="startup")
    return True


def load_active(db: Session, name: str, triggered_by: str = "mode-change", environment: Optional[str] = None) -> List[SyncRun]:
    """Bring a cloud up to date for its selected mode: first load, or the days missed while in the other mode.

    With `environment`, only that Live connection is loaded (one was just added or changed).
    """
    s = get_settings()
    today = local_today()
    runs = []
    for provider in connectors_for(name, db):
        if environment and provider.environment != environment:
            continue
        latest = _cost_date(db, func.max, name, provider)
        if latest is None:
            job, start = "backfill", today - timedelta(days=s.BACKFILL_DAYS)
        else:
            job, start = "manual", min(latest, today - timedelta(days=s.SYNC_LOOKBACK_DAYS))
        runs.append(sync_provider(db, name, provider, job=job, cost_start=start, cost_end=today + timedelta(days=1), metrics_hours=24 * 7, metrics_step=60, triggered_by=triggered_by))
    return runs


def extend_history(db: Session) -> List[SyncRun]:
    """If BACKFILL_DAYS was raised after the first start, fetch the older days that are missing.

    Runs once at startup; costs only one provider call per connector and only when there is a gap.
    """
    s = get_settings()
    target = local_today() - timedelta(days=s.BACKFILL_DAYS)
    runs = []
    for name, provider in get_connectors(db):
        earliest = _cost_date(db, func.min, name, provider)
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
