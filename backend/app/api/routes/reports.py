"""Cost reports for any date range (this month, last 6 months, a custom range...), as JSON or CSV."""
import calendar
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_filters, validate_range
from app.core.database import get_db
from app.models import CostRecord, User
from app.services import analytics
from app.services.analytics import Filters
from app.services.ingestion import local_today

router = APIRouter(prefix="/reports", tags=["reports"])


def _fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%b %Y')}"


def range_label(start: date, end: date) -> str:
    last = calendar.monthrange(start.year, start.month)[1]
    if start.day == 1 and start.year == end.year and start.month == end.month:
        return start.strftime("%B %Y") + ("" if end.day == last else " (to date)")
    return f"{_fmt(start)} – {_fmt(end)}"


def build_report(db: Session, f: Filters) -> dict:
    """Report for f.start..f.end compared with the previous period of equal length."""
    days = f.days
    budget_view = analytics.budget_info(db, f, 0, 0)  # the selected cloud's budget, or the all-clouds one
    monthly_budget = budget_view["budget"]
    spans = analytics.month_spans(f.start, f.end)
    # budget for the range = each month's budget pro-rated by the days of that month inside the range
    budget = sum(monthly_budget * sp["days_covered"] / sp["days_in_month"] for sp in spans)
    total = analytics.total_cost(db, f)
    prev_f = f.shifted(f.start - timedelta(days=days), f.start - timedelta(days=1))
    prev_total = analytics.total_cost(db, prev_f)
    recs = analytics.recommendations(db, f)
    months = analytics.monthly(db, f, None, "provider")
    data_from = db.scalar(select(func.min(CostRecord.usage_date)).where(analytics._cost_where(f, with_dates=False)))
    for m in months["months"]:
        m_budget = monthly_budget * m["days_covered"] / m["days_in_month"]
        m["budget"] = round(m_budget, 2)
        m["budget_used_pct"] = round(m["total"] / m_budget * 100, 2) if m_budget else None
    return {
        "label": range_label(f.start, f.end),
        "filters": f.describe(),
        "period": {"start": f.start.isoformat(), "end": f.end.isoformat(), "days": days},
        "previous_period": {
            "start": prev_f.start.isoformat(),
            "end": prev_f.end.isoformat(),
            "complete": bool(data_from and data_from <= prev_f.start),
            "data_from": data_from.isoformat() if data_from else None,
        },
        "total": round(total, 2),
        "daily_average": round(total / days, 2),
        "previous_total": round(prev_total, 2),
        "change_pct": analytics._pct(total, prev_total),
        "budget": round(budget, 2),
        "monthly_budget": monthly_budget,
        "budget_scope": budget_view["scope"],
        "budget_applies_to_filtered_view": budget_view["applies_to_filtered_view"],
        "budget_used_pct": round(total / budget * 100, 2) if budget else None,
        "monthly": months,
        "by_provider": analytics.breakdown(db, f, "provider"),
        "by_environment": analytics.breakdown(db, f, "environment"),
        "by_resource_type": analytics.breakdown(db, f, "resource_type"),
        "top_services": analytics.breakdown(db, f, "service", 10),
        "top_resources": analytics.resources(db, f, limit=10),
        "anomalies": analytics.anomalies(db, f),
        "recommendations": recs[:10],
        "potential_savings": round(sum(r["monthly_savings"] for r in recs), 2),
    }


def report_csv(rep: dict) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    p = rep["period"]
    w.writerow(["CloudLens cost report", rep["label"]])
    w.writerow(["Period", p["start"], p["end"], f'{p["days"]} days'])
    flt = rep["filters"]
    w.writerow(["Filters", "provider", ",".join(flt["providers"]) or "all", "environment", ",".join(flt["environments"]) or "all",
                "resource type", ",".join(flt["resource_types"]) or "all"])
    w.writerow(["Total (USD)", rep["total"], "Previous period", rep["previous_total"], "Change %", rep["change_pct"]])
    w.writerow(["Budget for period (USD)", rep["budget"], "Budget used %", rep["budget_used_pct"], "Budget scope", rep["budget_scope"]])
    w.writerow([])
    keys = rep["monthly"]["keys"]
    w.writerow(["Monthly breakdown"])
    w.writerow(["month", "from", "to", "days", *[f"{k}_usd" for k in keys], "total_usd", "budget_usd", "budget_used_pct", "change_pct", "change_basis"])
    for m in rep["monthly"]["months"]:
        w.writerow([m["month"], m["start"], m["end"], m["days_covered"], *[m.get(k, 0) for k in keys], m["total"], m["budget"],
                    m["budget_used_pct"], m["change_pct"], m["change_basis"]])
    w.writerow([])
    for section in ("by_provider", "by_environment", "by_resource_type", "top_services"):
        w.writerow([section.replace("_", " ").title()])
        w.writerow(["key", "cost_usd", "share_pct", "previous_usd", "change_pct"])
        for r in rep[section]:
            w.writerow([r["key"], r["cost"], r["pct"], r["previous"], r["change_pct"]])
        w.writerow([])
    w.writerow(["Anomalies"])
    w.writerow(["date", "provider", "cost_usd", "baseline_usd", "change_pct"])
    for a in rep["anomalies"]:
        w.writerow([a["date"], a["provider"], a["cost"], a["baseline"], a["change_pct"]])
    w.writerow([])
    w.writerow(["Recommendations"])
    w.writerow(["resource", "provider", "action", "monthly_cost", "monthly_savings", "detail"])
    for r in rep["recommendations"]:
        w.writerow([r["resource"], r["provider"], r["action"], r["monthly_cost"], r["monthly_savings"], r["detail"]])
    name = f'cloudlens_report_{p["start"]}_to_{p["end"]}.csv'
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/summary")
def summary_report(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Report for any range: `start`/`end` (validated: not in the future, start <= end, max 731 days)."""
    return build_report(db, f)


@router.get("/summary.csv")
def summary_csv(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return report_csv(build_report(db, f))


# ---------------------------------------------------------------- calendar-month shortcuts (kept for API clients)
def _month_filters(month: str | None) -> Filters:
    today = local_today()
    if not month:
        first = today.replace(day=1)
    else:
        try:
            first = date.fromisoformat(f"{month}-01")
        except ValueError:
            raise HTTPException(422, "month must be YYYY-MM")
    if first > today:
        raise HTTPException(422, f"{first.strftime('%B %Y')} is in the future.")
    last = min(first.replace(day=calendar.monthrange(first.year, first.month)[1]), today)
    validate_range(first, last, today)
    return Filters(first, last)


@router.get("/monthly")
def monthly_report(month: str | None = Query(None, description="YYYY-MM, default current month"), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return build_report(db, _month_filters(month))


@router.get("/monthly.csv")
def monthly_csv(month: str | None = Query(None), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return report_csv(build_report(db, _month_filters(month)))
