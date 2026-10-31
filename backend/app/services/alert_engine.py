"""Alert rule evaluation, Prometheus export, and Alertmanager webhook handling."""
from __future__ import annotations

import hashlib
import logging
import operator
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AlertEvent, AlertRule, Resource, ResourceMetric, SyncRun
from app.services import analytics, notifier, prom_metrics, settings_service
from app.services.analytics import Filters
from app.services.ingestion import local_today

log = logging.getLogger("cloudlens.alerts")
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
UNITS = {
    "daily_cost": "USD", "mtd_cost": "USD", "budget_used_pct": "%", "forecast_budget_pct": "%",
    "cost_anomaly_pct": "%", "resource_cpu": "%", "resource_memory": "%", "idle_resource_count": "resources",
}


def _scope(rule: AlertRule) -> Filters:
    today = local_today()
    return Filters(
        start=today - timedelta(days=1),
        end=today - timedelta(days=1),
        providers=[rule.provider] if rule.provider else [],
        environments=[rule.environment] if rule.environment else [],
        resource_types=[rule.resource_type] if rule.resource_type else [],
    )


def _resource_extreme(db: Session, f: Filters, field: str, threshold: float, op: str) -> Tuple[Optional[float], str]:
    """Highest (or lowest for < operators) recent value across resources in scope + offenders."""
    since = datetime.now(timezone.utc) - timedelta(minutes=max(30, get_settings().METRICS_INTERVAL_MINUTES * 3))
    col = getattr(ResourceMetric, field)
    latest_ts = select(ResourceMetric.resource_pk, func.max(ResourceMetric.ts).label("mts")).where(
        ResourceMetric.ts >= since, col.is_not(None)
    ).group_by(ResourceMetric.resource_pk).subquery()
    rows = db.execute(
        select(Resource.name, col)
        .join(ResourceMetric, ResourceMetric.resource_pk == Resource.id)
        .join(latest_ts, (latest_ts.c.resource_pk == ResourceMetric.resource_pk) & (latest_ts.c.mts == ResourceMetric.ts))
        .where(analytics._res_where(f))
    ).all()
    if not rows:
        return None, "no recent samples"
    cmp = OPS[op]
    offenders = sorted([(n, v) for n, v in rows if cmp(v, threshold)], key=lambda x: x[1], reverse=op in (">", ">="))
    value = max(v for _, v in rows) if op in (">", ">=") else min(v for _, v in rows)
    detail = ", ".join(f"{n} ({v:.1f}%)" for n, v in offenders[:5]) or "none"
    return round(value, 2), f"Offenders: {detail}"


def compute_value(db: Session, rule: AlertRule) -> Tuple[Optional[float], str]:
    f = _scope(rule)
    today = local_today()
    yesterday = today - timedelta(days=1)
    m = rule.metric
    if m == "daily_cost":
        v = analytics.total_cost(db, f)
        return round(v, 2), f"Cost on {yesterday.isoformat()}"
    if m in ("mtd_cost", "budget_used_pct", "forecast_budget_pct"):
        mtd = analytics.month_to_date(db, f)
        if m == "mtd_cost":
            return mtd["mtd"], f"Month to date ({today.strftime('%b %Y')})"
        budget = settings_service.budget_for(db, rule.provider)
        base = mtd["mtd"] if m == "budget_used_pct" else mtd["forecast"]
        label = "Month to date" if m == "budget_used_pct" else "Forecast"
        return (round(base / budget * 100, 2) if budget else None), f"{label} ${base:,.0f} of ${budget:,.0f} budget"
    if m == "cost_anomaly_pct":
        day = analytics.total_cost(db, f)
        prior = analytics.daily_totals(db, f.shifted(yesterday - timedelta(days=7), yesterday - timedelta(days=1)))
        if len(prior) < 4:
            return None, "not enough history"
        avg = sum(prior.values()) / len(prior)
        if not avg:
            return None, "no baseline"
        return round((day - avg) / avg * 100, 2), f"${day:,.0f} on {yesterday.isoformat()} vs 7-day average ${avg:,.0f}"
    if m == "resource_cpu":
        return _resource_extreme(db, f, "cpu_percent", rule.threshold, rule.operator)
    if m == "resource_memory":
        return _resource_extreme(db, f, "memory_percent", rule.threshold, rule.operator)
    if m == "idle_resource_count":
        rows = analytics.resources(db, f, status="idle", limit=1000)
        return float(len(rows)), "Idle: " + (", ".join(r["name"] for r in rows[:5]) or "none")
    return None, f"unknown metric {m}"


def _labels(rule: AlertRule) -> Dict[str, str]:
    return {
        "rule_id": str(rule.id), "rule_name": rule.name, "metric": rule.metric, "severity": rule.severity,
        "provider": rule.provider or "all", "environment": rule.environment or "all",
    }


def evaluate_all(db: Session) -> List[Dict[str, object]]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    prom_metrics.rule_value.clear()
    prom_metrics.rule_threshold.clear()
    prom_metrics.rule_breached.clear()
    results = []
    for rule in db.execute(select(AlertRule).where(AlertRule.enabled.is_(True))).scalars().all():
        try:
            value, detail = compute_value(db, rule)
        except Exception as exc:  # never let one bad rule stop the others
            log.exception("rule %s failed", rule.id)
            value, detail = None, f"error: {exc}"
        breached = value is not None and OPS[rule.operator](value, rule.threshold)
        previous = rule.state
        rule.last_value = value
        rule.last_detail = detail[:1000]
        rule.last_evaluated_at = now
        rule.state = "firing" if breached else "ok"
        labels = _labels(rule)
        if value is not None:
            prom_metrics.rule_value.labels(**labels).set(value)
        prom_metrics.rule_threshold.labels(**labels).set(rule.threshold)
        prom_metrics.rule_breached.labels(**labels).set(1 if breached else 0)
        if s.ALERT_DELIVERY == "direct" and previous != rule.state:
            record_event(db, rule, "firing" if breached else "resolved", source="direct", fingerprint=f"direct-{rule.id}", starts_at=now)
        results.append({"rule_id": rule.id, "value": value, "breached": breached, "detail": detail})
    # disabled rules are always "ok"
    for rule in db.execute(select(AlertRule).where(AlertRule.enabled.is_(False), AlertRule.state != "ok")).scalars().all():
        rule.state = "ok"
    db.commit()
    return results


def describe(rule: AlertRule, value: Optional[float]) -> Tuple[str, str]:
    unit = UNITS.get(rule.metric, "")
    if unit == "USD":
        fmt = lambda v: f"${v:,.2f}"  # noqa: E731
    elif unit == "%":
        fmt = lambda v: f"{v:,.1f}%"  # noqa: E731
    else:
        fmt = lambda v: f"{v:,.0f} {unit}"  # noqa: E731
    val = fmt(value) if value is not None else "n/a"
    title = rule.name
    msg = f"{rule.metric.replace('_', ' ')} is {val} (threshold {rule.operator} {fmt(rule.threshold)}). {rule.last_detail or ''}".strip()
    return title, msg


def record_event(
    db: Session,
    rule: Optional[AlertRule],
    status: str,
    source: str,
    fingerprint: str,
    starts_at: datetime,
    ends_at: Optional[datetime] = None,
    title: Optional[str] = None,
    message: Optional[str] = None,
    severity: Optional[str] = None,
    labels: Optional[dict] = None,
) -> AlertEvent:
    default_channel = settings_service.get_value(db, "notification_channel")
    if rule is not None:
        t, msg = describe(rule, rule.last_value)
        title, message = title or t, message or msg
        severity = severity or rule.severity
        channels = notifier.resolve_channels(rule.channels, default_channel)
        fields = {
            "Severity": severity.title(), "Provider": (rule.provider or "all").upper(), "Environment": (rule.environment or "all").title(),
            "Value": f"{rule.last_value:,.2f}" if rule.last_value is not None else "n/a", "Threshold": f"{rule.operator} {rule.threshold:,.2f}",
        }
    else:
        channels = notifier.resolve_channels("default", default_channel)
        severity = severity or "warning"
        fields = {"Severity": severity.title(), **{k: v for k, v in (labels or {}).items() if k not in ("severity",)}}
    event = AlertEvent(
        rule_id=rule.id if rule else None, fingerprint=fingerprint[:64], status=status, severity=severity,
        title=(title or "Alert")[:255], message=message or "", value=rule.last_value if rule else None,
        threshold=rule.threshold if rule else None, labels=labels or (_labels(rule) if rule else {}), source=source,
        starts_at=starts_at, ends_at=ends_at, notified_channels=",".join(channels),
    )
    status_sent, err = notifier.send(channels, event.title, event.message, severity, status, fields, settings_service.webhook_urls(db))
    event.notification_status = status_sent
    event.notification_error = err
    db.add(event)
    db.commit()
    return event


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value or value.startswith("0001"):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def handle_alertmanager(db: Session, payload: dict) -> List[int]:
    """Process an Alertmanager webhook payload (version 4)."""
    created: List[int] = []
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {}) or {}
        annotations = alert.get("annotations", {}) or {}
        status = alert.get("status", payload.get("status", "firing"))
        starts = _parse_ts(alert.get("startsAt")) or datetime.now(timezone.utc)
        ends = _parse_ts(alert.get("endsAt")) if status == "resolved" else None
        fp = alert.get("fingerprint") or hashlib.sha1(str(sorted(labels.items())).encode()).hexdigest()
        # de-duplicate repeats of the same notification (Alertmanager re-sends on repeat_interval)
        exists = db.execute(
            select(AlertEvent.id).where(AlertEvent.fingerprint == fp[:64], AlertEvent.status == status, AlertEvent.starts_at == starts)
        ).first()
        if exists:
            continue
        rule = None
        if labels.get("rule_id", "").isdigit():
            rule = db.get(AlertRule, int(labels["rule_id"]))
        event = record_event(
            db, rule, status, source="alertmanager", fingerprint=fp, starts_at=starts, ends_at=ends,
            title=None if rule else annotations.get("summary") or labels.get("alertname"),
            message=None if rule else annotations.get("description", ""),
            severity=labels.get("severity"), labels=labels,
        )
        created.append(event.id)
    return created


def refresh_metrics(db: Session) -> None:
    """Update the cost / utilization / sync gauges exposed to Prometheus."""
    today = local_today()
    yesterday = today - timedelta(days=1)
    budgets = settings_service.get_value(db, "provider_budgets_usd") or {}
    total_budget = float(settings_service.get_value(db, "monthly_budget_usd") or 0)
    total_mtd = 0.0
    prom_metrics.cost_last_day.clear()
    for prov in get_settings().enabled_providers:
        f = Filters(yesterday, yesterday, providers=[prov])
        m = analytics.month_to_date(db, f)
        total_mtd += m["mtd"]
        prom_metrics.cost_mtd.labels(provider=prov).set(m["mtd"])
        prom_metrics.cost_forecast.labels(provider=prov).set(m["forecast"])
        for row in analytics.breakdown(db, f, "environment"):
            prom_metrics.cost_last_day.labels(provider=prov, environment=row["key"]).set(row["cost"])
        if budgets.get(prov):
            prom_metrics.budget_used.labels(scope=prov).set(m["mtd"] / float(budgets[prov]))
        last_ok = db.execute(
            select(SyncRun.finished_at).where(SyncRun.provider == prov, SyncRun.status == "success").order_by(SyncRun.finished_at.desc()).limit(1)
        ).scalar()
        if last_ok:
            prom_metrics.sync_last_success.labels(provider=prov).set(last_ok.timestamp())
        last = db.execute(select(SyncRun.status).where(SyncRun.provider == prov).order_by(SyncRun.started_at.desc()).limit(1)).scalar()
        prom_metrics.sync_last_ok.labels(provider=prov).set(0 if last == "failed" else 1)
    if total_budget:
        prom_metrics.budget_used.labels(scope="all").set(total_mtd / total_budget)
    prom_metrics.resource_cpu.clear()
    prom_metrics.resource_mem.clear()
    for r in analytics.resources(db, Filters(yesterday, yesterday), limit=1000):
        lbl = dict(provider=r["provider"], resource=r["name"], environment=r["environment"], resource_type=r["resource_type"])
        if r["cpu"] is not None:
            prom_metrics.resource_cpu.labels(**lbl).set(r["cpu"])
        if r["memory"] is not None:
            prom_metrics.resource_mem.labels(**lbl).set(r["memory"])
