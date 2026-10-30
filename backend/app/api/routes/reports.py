import calendar
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.services import analytics, settings_service
from app.services.analytics import Filters
from app.services.ingestion import local_today

router = APIRouter(prefix="/reports", tags=["reports"])


def _month_range(month: str | None):
    today = local_today()
    if not month:
        first = today.replace(day=1)
    else:
        try:
            first = date.fromisoformat(f"{month}-01")
        except ValueError:
            raise HTTPException(422, "month must be YYYY-MM")
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, min(last, today)


def build_monthly(db: Session, month: str | None) -> dict:
    first, last = _month_range(month)
    f = Filters(first, last)
    budget = float(settings_service.get_value(db, "monthly_budget_usd"))
    total = analytics.total_cost(db, f)
    prev_last = first - timedelta(days=1)
    prev_f = Filters(prev_last.replace(day=1), prev_last)
    prev_total = analytics.total_cost(db, prev_f)
    recs = analytics.recommendations(db, f)
    return {
        "month": first.strftime("%Y-%m"),
        "label": first.strftime("%B %Y"),
        "period": {"start": first.isoformat(), "end": last.isoformat(), "complete": last.day == calendar.monthrange(first.year, first.month)[1]},
        "total": round(total, 2),
        "previous_month_total": round(prev_total, 2),
        "change_pct": analytics._pct(total, prev_total),
        "budget": budget,
        "budget_used_pct": round(total / budget * 100, 2) if budget else None,
        "by_provider": analytics.breakdown(db, f, "provider"),
        "by_environment": analytics.breakdown(db, f, "environment"),
        "by_resource_type": analytics.breakdown(db, f, "resource_type"),
        "top_services": analytics.breakdown(db, f, "service", 10),
        "top_resources": analytics.resources(db, f, limit=10),
        "anomalies": analytics.anomalies(db, f),
        "recommendations": recs[:10],
        "potential_savings": round(sum(r["monthly_savings"] for r in recs), 2),
    }


@router.get("/monthly")
def monthly_report(month: str | None = Query(None, description="YYYY-MM, default current month"), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return build_monthly(db, month)


@router.get("/monthly.csv")
def monthly_csv(month: str | None = Query(None), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rep = build_monthly(db, month)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["CloudLens monthly cost report", rep["label"]])
    w.writerow(["Total (USD)", rep["total"], "Previous month", rep["previous_month_total"], "Change %", rep["change_pct"]])
    w.writerow([])
    for section in ("by_provider", "by_environment", "by_resource_type", "top_services"):
        w.writerow([section.replace("_", " ").title()])
        w.writerow(["key", "cost_usd", "share_pct", "previous_usd", "change_pct"])
        for r in rep[section]:
            w.writerow([r["key"], r["cost"], r["pct"], r["previous"], r["change_pct"]])
        w.writerow([])
    w.writerow(["Recommendations"])
    w.writerow(["resource", "provider", "action", "monthly_cost", "monthly_savings", "detail"])
    for r in rep["recommendations"]:
        w.writerow([r["resource"], r["provider"], r["action"], r["monthly_cost"], r["monthly_savings"], r["detail"]])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="cloudlens_report_{rep["month"]}.csv"'})
