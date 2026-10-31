"""Analytics on the stored data: summaries, trends, breakdowns, utilization, anomalies, recommendations.

All SQL is portable (GROUP BY on plain columns); month bucketing and moving averages are done in
Python so the same code runs on PostgreSQL in production and SQLite in unit tests.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import AlertEvent, AlertRule, CostRecord, Resource, ResourceMetric
from app.services import settings_service
from app.services.ingestion import local_today

DIMENSIONS = {
    "provider": CostRecord.provider,
    "environment": CostRecord.environment,
    "resource_type": CostRecord.resource_type,
    "service": CostRecord.service,
    "region": CostRecord.region,
    "account": CostRecord.account_id,
}
OVER_UTILIZED = 80.0


@dataclass
class Filters:
    start: date
    end: date  # inclusive
    providers: List[str] = field(default_factory=list)
    environments: List[str] = field(default_factory=list)
    resource_types: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def shifted(self, start: date, end: date) -> "Filters":
        return Filters(start, end, self.providers, self.environments, self.resource_types, self.services, self.regions)

    def describe(self) -> Dict[str, object]:
        return {
            "start": self.start.isoformat(), "end": self.end.isoformat(), "days": self.days,
            "providers": self.providers, "environments": self.environments,
            "resource_types": self.resource_types, "services": self.services, "regions": self.regions,
        }


def _cost_where(f: Filters, with_dates: bool = True):
    conds = []
    if with_dates:
        conds += [CostRecord.usage_date >= f.start, CostRecord.usage_date <= f.end]
    if f.providers:
        conds.append(CostRecord.provider.in_(f.providers))
    if f.environments:
        conds.append(CostRecord.environment.in_(f.environments))
    if f.resource_types:
        conds.append(CostRecord.resource_type.in_(f.resource_types))
    if f.services:
        conds.append(CostRecord.service.in_(f.services))
    if f.regions:
        conds.append(CostRecord.region.in_(f.regions))
    return and_(*conds) if conds else True


def _res_where(f: Filters):
    conds = []
    if f.providers:
        conds.append(Resource.provider.in_(f.providers))
    if f.environments:
        conds.append(Resource.environment.in_(f.environments))
    if f.resource_types:
        conds.append(Resource.resource_type.in_(f.resource_types))
    if f.regions:
        conds.append(Resource.region.in_(f.regions))
    return and_(*conds) if conds else True


def _pct(cur: float, prev: float) -> Optional[float]:
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 2)


def total_cost(db: Session, f: Filters) -> float:
    return float(db.scalar(select(func.coalesce(func.sum(CostRecord.cost_usd), 0)).where(_cost_where(f))) or 0)


def daily_totals(db: Session, f: Filters) -> Dict[date, float]:
    rows = db.execute(
        select(CostRecord.usage_date, func.sum(CostRecord.cost_usd)).where(_cost_where(f)).group_by(CostRecord.usage_date)
    ).all()
    return {d: float(v) for d, v in rows}


def daily_series(db: Session, f: Filters, group_by: Optional[str] = None) -> Dict[str, object]:
    """Daily cost per day (optionally split by a dimension), zero-filled, with a 7-day moving average."""
    days = [f.start + timedelta(days=i) for i in range(f.days)]
    series: Dict[str, Dict[date, float]] = defaultdict(dict)
    if group_by:
        col = DIMENSIONS[group_by]
        rows = db.execute(
            select(CostRecord.usage_date, col, func.sum(CostRecord.cost_usd)).where(_cost_where(f)).group_by(CostRecord.usage_date, col)
        ).all()
        for d, k, v in rows:
            series[k][d] = float(v)
    totals = daily_totals(db, f)
    points = []
    window: List[float] = []
    for d in days:
        total = round(totals.get(d, 0.0), 2)
        window.append(total)
        if len(window) > 7:
            window.pop(0)
        point = {"date": d.isoformat(), "total": total, "ma7": round(sum(window) / len(window), 2)}
        for k, vals in series.items():
            point[k] = round(vals.get(d, 0.0), 2)
        points.append(point)
    return {"group_by": group_by, "keys": sorted(series.keys()), "points": points}


def breakdown(db: Session, f: Filters, dim: str, limit: int = 50) -> List[Dict[str, object]]:
    col = DIMENSIONS[dim]
    prev_f = f.shifted(f.start - timedelta(days=f.days), f.start - timedelta(days=1))
    cur = dict(db.execute(select(col, func.sum(CostRecord.cost_usd)).where(_cost_where(f)).group_by(col)).all())
    prev = dict(db.execute(select(col, func.sum(CostRecord.cost_usd)).where(_cost_where(prev_f)).group_by(col)).all())
    total = sum(float(v) for v in cur.values()) or 1.0
    rows = [
        {
            "key": k,
            "cost": round(float(v), 2),
            "pct": round(float(v) / total * 100, 2),
            "previous": round(float(prev.get(k, 0) or 0), 2),
            "change_pct": _pct(float(v), float(prev.get(k, 0) or 0)),
        }
        for k, v in cur.items()
    ]
    rows.sort(key=lambda r: r["cost"], reverse=True)
    return rows[:limit]


def month_to_date(db: Session, f: Filters, today: Optional[date] = None) -> Dict[str, float]:
    today = today or local_today()
    first = today.replace(day=1)
    mf = f.shifted(first, today)
    daily = daily_totals(db, mf)
    mtd = sum(daily.values())
    full_days = [daily.get(first + timedelta(days=i), 0.0) for i in range((today - first).days)]
    last7 = daily_totals(db, f.shifted(today - timedelta(days=7), today - timedelta(days=1)))
    avg7 = sum(last7.values()) / 7
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    remaining = days_in_month - (today.day - 1)
    forecast = sum(full_days) + avg7 * remaining
    # same period last month for comparison
    lm_end = first - timedelta(days=1)
    lm_first = lm_end.replace(day=1)
    lm_same = lm_first + timedelta(days=min(today.day, lm_end.day) - 1)
    last_month_same = total_cost(db, f.shifted(lm_first, lm_same))
    last_month_total = total_cost(db, f.shifted(lm_first, lm_end))
    return {
        "mtd": round(mtd, 2),
        "forecast": round(forecast, 2),
        "avg_daily_7d": round(avg7, 2),
        "last_month_same_period": round(last_month_same, 2),
        "last_month_total": round(last_month_total, 2),
        "mtd_change_pct": _pct(mtd, last_month_same),
        "days_in_month": days_in_month,
        "day_of_month": today.day,
    }


def budget_info(db: Session, f: Filters, mtd: float, forecast: float) -> Dict[str, object]:
    provider = f.providers[0] if len(f.providers) == 1 else None
    if f.providers and len(f.providers) > 1:
        budgets = settings_service.get_value(db, "provider_budgets_usd") or {}
        budget = sum(float(budgets.get(p, 0)) for p in f.providers)
        scope = ",".join(f.providers)
    else:
        budget = settings_service.budget_for(db, provider)
        scope = provider or "all"
    partial = bool(f.environments or f.resource_types or f.services or f.regions)
    return {
        "budget": round(budget, 2),
        "scope": scope,
        "applies_to_filtered_view": not partial,
        "used_pct": round(mtd / budget * 100, 2) if budget else None,
        "forecast_pct": round(forecast / budget * 100, 2) if budget else None,
    }


def alert_counts(db: Session) -> Dict[str, int]:
    rows = db.execute(select(AlertRule.severity, func.count()).where(AlertRule.enabled.is_(True), AlertRule.state == "firing").group_by(AlertRule.severity)).all()
    counts = {"critical": 0, "warning": 0, "info": 0}
    for sev, n in rows:
        counts[sev] = n
    counts["total"] = sum(counts.values())
    return counts


def summary(db: Session, f: Filters) -> Dict[str, object]:
    cur = total_cost(db, f)
    prev = total_cost(db, f.shifted(f.start - timedelta(days=f.days), f.start - timedelta(days=1)))
    mtd = month_to_date(db, f)
    recs = recommendations(db, f)
    return {
        "filters": f.describe(),
        "period_total": round(cur, 2),
        "previous_period_total": round(prev, 2),
        "period_change_pct": _pct(cur, prev),
        "daily_average": round(cur / f.days, 2),
        "month": mtd,
        "budget": budget_info(db, f, mtd["mtd"], mtd["forecast"]),
        "alerts": alert_counts(db),
        "savings": {"monthly_total": round(sum(r["monthly_savings"] for r in recs), 2), "count": len(recs)},
        "resources": resource_counts(db, f),
    }


def month_spans(start: date, end: date, today: Optional[date] = None) -> List[Dict[str, object]]:
    """Calendar months touched by [start, end] with the part of each month that is covered.

    A month is `full` only when the range covers all its days and it has ended (a month that
    contains today is still accruing cost, so it counts as partial).
    """
    today = today or local_today()
    out = []
    m = start.replace(day=1)
    while m <= end:
        days_in = calendar.monthrange(m.year, m.month)[1]
        m_last = m.replace(day=days_in)
        c_start, c_end = max(start, m), min(end, m_last)
        out.append({
            "first": m, "last": m_last, "start": c_start, "end": c_end, "days_in_month": days_in,
            "days_covered": (c_end - c_start).days + 1, "full": c_start == m and c_end == m_last and m_last < today,
        })
        m = m_last + timedelta(days=1)
    return out


def monthly(db: Session, f: Filters, months: Optional[int] = None, group_by: Optional[str] = "provider") -> Dict[str, object]:
    """Cost per calendar month for the selected range (or the last `months` months up to f.end).

    Months only partly inside the range are flagged `partial`; their change vs the previous month is
    computed on the daily average (run rate) instead of the total, so a half month never looks like a drop.
    """
    if months:
        first = f.end.replace(day=1)
        for _ in range(months - 1):
            first = (first - timedelta(days=1)).replace(day=1)
        start, end = first, f.end
    else:
        start, end = f.start, f.end
    spans = month_spans(start, end)
    mf = f.shifted(start, end)
    col = DIMENSIONS[group_by] if group_by else None
    if col is not None:
        rows = db.execute(select(CostRecord.usage_date, col, func.sum(CostRecord.cost_usd)).where(_cost_where(mf)).group_by(CostRecord.usage_date, col)).all()
    else:
        rows = [(d, "total", v) for d, v in daily_totals(db, mf).items()]
    buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    keys = set()
    for d, k, v in rows:
        buckets[d.strftime("%Y-%m")][k] += float(v)
        keys.add(k)
    out = []
    prev = None
    for sp in spans:
        label = sp["first"].strftime("%Y-%m")
        vals = buckets.get(label, {})
        total = sum(vals.values())
        row = {
            "month": label,
            "label": sp["first"].strftime("%b %Y"),
            "start": sp["start"].isoformat(),
            "end": sp["end"].isoformat(),
            "total": round(total, 2),
            "partial": not sp["full"],
            "days_covered": sp["days_covered"],
            "days_in_month": sp["days_in_month"],
            "daily_average": round(total / sp["days_covered"], 2),
            "change_pct": None,
            "change_basis": None,
            **{k: round(vals.get(k, 0.0), 2) for k in keys},
        }
        if prev is not None:
            if sp["full"] and not prev["partial"]:
                row["change_pct"], row["change_basis"] = _pct(total, prev["total"]), "total"
            else:
                row["change_pct"], row["change_basis"] = _pct(row["daily_average"], prev["daily_average"]), "run_rate"
        out.append(row)
        prev = row
    if len(out) >= 2:  # backward compatible field used by older clients
        out[-1]["run_rate_change_pct"] = _pct(out[-1]["daily_average"], out[-2]["daily_average"])
    return {"group_by": group_by, "keys": sorted(keys), "start": start.isoformat(), "end": end.isoformat(), "months": out}


# ---------------------------------------------------------------- utilization & resources
def _latest_metrics(db: Session) -> Dict[int, ResourceMetric]:
    sub = select(ResourceMetric.resource_pk, func.max(ResourceMetric.ts).label("mts")).group_by(ResourceMetric.resource_pk).subquery()
    rows = db.execute(
        select(ResourceMetric).join(sub, and_(ResourceMetric.resource_pk == sub.c.resource_pk, ResourceMetric.ts == sub.c.mts))
    ).scalars().all()
    return {m.resource_pk: m for m in rows}


def _avg_metrics(db: Session, since: datetime) -> Dict[int, Dict[str, Optional[float]]]:
    rows = db.execute(
        select(
            ResourceMetric.resource_pk,
            func.avg(ResourceMetric.cpu_percent),
            func.avg(ResourceMetric.memory_percent),
            func.max(ResourceMetric.cpu_percent),
            func.avg(ResourceMetric.storage_percent),
        ).where(ResourceMetric.ts >= since).group_by(ResourceMetric.resource_pk)
    ).all()
    return {
        pk: {"cpu_avg": _r(c), "mem_avg": _r(m), "cpu_max": _r(mx), "storage_avg": _r(st)}
        for pk, c, m, mx, st in rows
    }


def _r(v) -> Optional[float]:
    return round(float(v), 2) if v is not None else None


def _resource_costs(db: Session, f: Filters) -> Dict[str, float]:
    rows = db.execute(
        select(CostRecord.resource_id, func.sum(CostRecord.cost_usd)).where(_cost_where(f), CostRecord.resource_id != "").group_by(CostRecord.resource_id)
    ).all()
    return {rid: float(v) for rid, v in rows}


def resource_status(latest_cpu: Optional[float], avg_cpu: Optional[float], storage: Optional[float], idle_threshold: float = 10.0) -> str:
    if latest_cpu is not None and latest_cpu >= OVER_UTILIZED:
        return "over_utilized"
    if storage is not None and storage >= 90:
        return "over_utilized"
    if avg_cpu is not None and avg_cpu < idle_threshold:
        return "idle"
    if latest_cpu is None and storage is None:
        return "no_metrics"
    return "healthy"


def resources(db: Session, f: Filters, search: str = "", status: str = "", sort: str = "cost", limit: int = 200) -> List[Dict[str, object]]:
    idle_thr = float(settings_service.get_value(db, "idle_cpu_threshold") or 10)
    q = select(Resource).where(_res_where(f))
    if search:
        like = f"%{search.lower()}%"
        q = q.where(func.lower(Resource.name).like(like) | func.lower(Resource.resource_id).like(like))
    items = db.execute(q).scalars().all()
    latest = _latest_metrics(db)
    avgs = _avg_metrics(db, datetime.now(timezone.utc) - timedelta(days=7))
    costs = _resource_costs(db, f)
    out = []
    for r in items:
        lm = latest.get(r.id)
        av = avgs.get(r.id, {})
        st = resource_status(lm.cpu_percent if lm else None, av.get("cpu_avg"), lm.storage_percent if lm else None, idle_thr)
        row = {
            "id": r.id, "name": r.name, "provider": r.provider, "resource_id": r.resource_id, "account_id": r.account_id,
            "resource_type": r.resource_type, "service": r.service, "environment": r.environment, "region": r.region,
            "sku": r.sku, "state": r.status, "cost": round(costs.get(r.resource_id, 0.0), 2),
            "cpu": lm.cpu_percent if lm else None, "memory": lm.memory_percent if lm else None,
            "storage": lm.storage_percent if lm else None, "cpu_avg_7d": av.get("cpu_avg"), "cpu_max_7d": av.get("cpu_max"),
            "mem_avg_7d": av.get("mem_avg"), "last_sample_at": lm.ts.isoformat() if lm else None, "status": st,
        }
        out.append(row)
    if status:
        out = [o for o in out if o["status"] == status]
    key = {"cost": lambda o: o["cost"], "cpu": lambda o: o["cpu"] or -1, "name": lambda o: o["name"]}.get(sort, lambda o: o["cost"])
    out.sort(key=key, reverse=sort != "name")
    return out[:limit]


def resource_counts(db: Session, f: Filters) -> Dict[str, int]:
    rows = resources(db, f, limit=10000)
    counts = {"total": len(rows), "over_utilized": 0, "idle": 0, "healthy": 0, "no_metrics": 0}
    for r in rows:
        counts[r["status"]] += 1
    return counts


def utilization(db: Session, f: Filters, hours: int = 168) -> Dict[str, object]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    base = select(Resource.provider, func.avg(ResourceMetric.cpu_percent), func.avg(ResourceMetric.memory_percent), func.max(ResourceMetric.cpu_percent)).join(
        Resource, Resource.id == ResourceMetric.resource_pk
    ).where(ResourceMetric.ts >= since, _res_where(f))
    per_provider = [
        {"provider": p, "cpu_avg": _r(c), "mem_avg": _r(m), "cpu_peak": _r(mx)}
        for p, c, m, mx in db.execute(base.group_by(Resource.provider)).all()
    ]
    # latest snapshot (real-time) per provider
    latest = _latest_metrics(db)
    res = {r.id: r for r in db.execute(select(Resource).where(_res_where(f))).scalars().all()}
    snap: Dict[str, List[float]] = defaultdict(list)
    snap_mem: Dict[str, List[float]] = defaultdict(list)
    for pk, m in latest.items():
        if pk in res and m.cpu_percent is not None:
            snap[res[pk].provider].append(m.cpu_percent)
        if pk in res and m.memory_percent is not None:
            snap_mem[res[pk].provider].append(m.memory_percent)
    for row in per_provider:
        vals = snap.get(row["provider"], [])
        mems = snap_mem.get(row["provider"], [])
        row["cpu_now"] = round(sum(vals) / len(vals), 2) if vals else None
        row["mem_now"] = round(sum(mems) / len(mems), 2) if mems else None
    # hourly average CPU trend (bucket in Python for portability)
    trend_rows = db.execute(
        select(ResourceMetric.ts, Resource.provider, ResourceMetric.cpu_percent).join(Resource, Resource.id == ResourceMetric.resource_pk).where(
            ResourceMetric.ts >= since, _res_where(f), ResourceMetric.cpu_percent.is_not(None)
        )
    ).all()
    bucket_hours = 1 if hours <= 48 else (6 if hours <= 24 * 14 else 24)
    buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for ts, prov, cpu in trend_rows:
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        b = ts.replace(minute=0, second=0, microsecond=0)
        b = b - timedelta(hours=b.hour % bucket_hours)
        buckets[b.isoformat()][prov].append(cpu)
    trend = []
    for k in sorted(buckets):
        point = {"ts": k}
        for prov, vals in buckets[k].items():
            point[prov] = round(sum(vals) / len(vals), 2)
        trend.append(point)
    counts = resource_counts(db, f)
    measured = counts["total"] - counts["no_metrics"]
    return {
        "window_hours": hours,
        "providers": sorted(per_provider, key=lambda r: r["provider"]),
        "trend": trend,
        "bucket_hours": bucket_hours,
        "counts": counts,
        "healthy_rate_pct": round(counts["healthy"] / measured * 100, 1) if measured else None,
        "threshold_pct": OVER_UTILIZED,
    }


def resource_detail(db: Session, pk: int, days: int = 30, f: Optional[Filters] = None) -> Optional[Dict[str, object]]:
    """Drill-down for one resource. Cost covers `f` (start..end) when given, else the last `days` days."""
    r = db.get(Resource, pk)
    if r is None:
        return None
    today = local_today()
    if f is None:
        f = Filters(today - timedelta(days=days - 1), today)
    days = f.days
    rows = db.execute(
        select(CostRecord.usage_date, func.sum(CostRecord.cost_usd)).where(
            CostRecord.resource_id == r.resource_id, CostRecord.usage_date >= f.start, CostRecord.usage_date <= f.end
        ).group_by(CostRecord.usage_date)
    ).all()
    cmap = {d: float(v) for d, v in rows}
    cost_series = [{"date": (f.start + timedelta(days=i)).isoformat(), "cost": round(cmap.get(f.start + timedelta(days=i), 0.0), 2)} for i in range(days)]
    since = datetime.now(timezone.utc) - timedelta(days=7)
    metrics = db.execute(
        select(ResourceMetric).where(ResourceMetric.resource_pk == pk, ResourceMetric.ts >= since).order_by(ResourceMetric.ts)
    ).scalars().all()
    listing = [x for x in resources(db, Filters(f.start, f.end, providers=[r.provider]), search=r.resource_id, limit=5) if x["id"] == pk]
    recs = [x for x in recommendations(db, Filters(f.start, f.end, providers=[r.provider])) if x["resource_pk"] == pk]
    return {
        "resource": listing[0] if listing else {"id": r.id, "name": r.name},
        "tags": r.tags or {},
        "first_seen_at": r.first_seen_at.isoformat() if r.first_seen_at else None,
        "cost_series": cost_series,
        "cost_total": round(sum(cmap.values()), 2),
        "period": {"start": f.start.isoformat(), "end": f.end.isoformat(), "days": days},
        "metrics": [
            {"ts": m.ts.isoformat(), "cpu": m.cpu_percent, "memory": m.memory_percent, "storage": m.storage_percent, "net_in": m.network_in_mb, "net_out": m.network_out_mb}
            for m in metrics
        ],
        "recommendations": recs,
    }


# ---------------------------------------------------------------- anomalies & optimization
def anomalies(db: Session, f: Filters, threshold_pct: float = 40.0) -> List[Dict[str, object]]:
    """Days where a provider's cost exceeded its trailing 7-day average by more than threshold_pct."""
    lookback = f.shifted(f.start - timedelta(days=7), f.end)
    rows = db.execute(
        select(CostRecord.usage_date, CostRecord.provider, func.sum(CostRecord.cost_usd)).where(_cost_where(lookback)).group_by(CostRecord.usage_date, CostRecord.provider)
    ).all()
    per: Dict[str, Dict[date, float]] = defaultdict(dict)
    for d, p, v in rows:
        per[p][d] = float(v)
    today = local_today()
    out = []
    for prov, vals in per.items():
        d = f.start
        while d <= f.end:
            if d >= today:  # today is partial
                break
            prior = [vals.get(d - timedelta(days=i)) for i in range(1, 8)]
            prior = [p for p in prior if p is not None]
            if len(prior) >= 4 and d in vals:
                avg = sum(prior) / len(prior)
                change = _pct(vals[d], avg)
                if change is not None and change >= threshold_pct:
                    out.append({"date": d.isoformat(), "provider": prov, "cost": round(vals[d], 2), "baseline": round(avg, 2), "change_pct": change})
            d += timedelta(days=1)
    out.sort(key=lambda a: a["date"], reverse=True)
    return out


def recommendations(db: Session, f: Filters) -> List[Dict[str, object]]:
    """Rule-based cost optimization recommendations with estimated monthly savings."""
    idle_thr = float(settings_service.get_value(db, "idle_cpu_threshold") or 10)
    under_thr = float(settings_service.get_value(db, "underutilized_cpu_threshold") or 30)
    today = local_today()
    month_f = Filters(today - timedelta(days=30), today - timedelta(days=1), f.providers, f.environments, f.resource_types)
    costs = _resource_costs(db, month_f)
    avgs = _avg_metrics(db, datetime.now(timezone.utc) - timedelta(days=7))
    out = []
    for r in db.execute(select(Resource).where(_res_where(f))).scalars().all():
        monthly_cost = costs.get(r.resource_id, 0.0)
        if monthly_cost <= 0:
            continue
        av = avgs.get(r.id, {})
        cpu, mem, stor = av.get("cpu_avg"), av.get("mem_avg"), av.get("storage_avg")
        rec = None
        if cpu is not None and cpu < idle_thr and r.resource_type in ("compute", "containers", "database"):
            if r.environment == "production":
                rec = ("rightsize", f"Average CPU {cpu:.1f}% over 7 days. Downsize to a smaller instance family.", 0.5)
            else:
                rec = ("stop_idle", f"Idle: average CPU {cpu:.1f}% over 7 days. Stop or schedule it off outside working hours.", 0.9)
        elif cpu is not None and cpu < under_thr and (mem is None or mem < 50) and r.resource_type in ("compute", "containers", "database"):
            rec = ("rightsize", f"Under-utilized: CPU {cpu:.1f}%, memory {mem or 0:.1f}%. Move one size down.", 0.4)
        elif r.environment in ("development", "staging") and r.resource_type in ("compute", "containers") and cpu is not None:
            rec = ("schedule", "Non-production workload running 24x7. Schedule shutdown nights and weekends.", 0.6)
        elif stor is not None and stor < 20 and r.resource_type == "storage":
            rec = ("storage_tier", f"Only {stor:.0f}% used. Move to an infrequent-access / archive tier or add lifecycle rules.", 0.45)
        if rec:
            out.append({
                "resource_pk": r.id, "resource": r.name, "provider": r.provider, "environment": r.environment,
                "resource_type": r.resource_type, "action": rec[0], "detail": rec[1],
                "monthly_cost": round(monthly_cost, 2), "monthly_savings": round(monthly_cost * rec[2], 2),
                "cpu_avg_7d": cpu,
            })
    out.sort(key=lambda x: x["monthly_savings"], reverse=True)
    return out


def recent_events(db: Session, limit: int = 10) -> List[AlertEvent]:
    return db.execute(select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(limit)).scalars().all()
