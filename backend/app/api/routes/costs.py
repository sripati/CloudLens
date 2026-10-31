import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import MAX_RANGE_DAYS, get_current_user, get_filters
from app.core.config import get_settings
from app.core.database import get_db
from app.models import CostRecord, User
from app.services import analytics
from app.services.analytics import DIMENSIONS, Filters, _cost_where
from app.services.ingestion import local_today

router = APIRouter(prefix="/costs", tags=["costs"])


def _dim(value: Optional[str]) -> Optional[str]:
    if value in (None, "", "none"):
        return None
    if value not in DIMENSIONS:
        raise HTTPException(422, f"group_by must be one of {sorted(DIMENSIONS)}")
    return value


@router.get("/daily")
def daily(group_by: Optional[str] = Query("provider"), f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return analytics.daily_series(db, f, _dim(group_by))


@router.get("/breakdown")
def breakdown(dimension: str = Query("service"), limit: int = Query(50, le=200), f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if dimension not in DIMENSIONS:
        raise HTTPException(422, f"dimension must be one of {sorted(DIMENSIONS)}")
    return {"dimension": dimension, "rows": analytics.breakdown(db, f, dimension, limit)}


@router.get("/monthly")
def monthly(
    months: Optional[int] = Query(None, ge=1, le=24, description="Optional: last N months ending at `end`. Default: the months inside start..end"),
    group_by: Optional[str] = Query("provider"),
    f: Filters = Depends(get_filters),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return analytics.monthly(db, f, months, _dim(group_by))


@router.get("/date-bounds")
def date_bounds(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Dates the date-range picker may offer: data from `min_date`, never after `today` (server timezone)."""
    today = local_today()
    lo, hi = db.execute(select(func.min(CostRecord.usage_date), func.max(CostRecord.usage_date))).one()
    return {
        "today": today.isoformat(),
        "min_date": (lo or today).isoformat(),
        "max_date": min(hi or today, today).isoformat(),
        "max_range_days": MAX_RANGE_DAYS,
        "timezone": get_settings().TIMEZONE,
    }


@router.get("/anomalies")
def anomalies(threshold_pct: float = Query(40, ge=5, le=500), f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return analytics.anomalies(db, f, threshold_pct)


@router.get("/filters")
def filter_options(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Distinct values present in the data, used to populate filter dropdowns."""
    def values(col):
        return sorted(v for (v,) in db.execute(select(col).distinct()).all() if v)

    return {
        "providers": values(CostRecord.provider),
        "environments": values(CostRecord.environment),
        "resource_types": values(CostRecord.resource_type),
        "services": values(CostRecord.service),
        "regions": values(CostRecord.region),
        "accounts": values(CostRecord.account_id),
    }


@router.get("/export")
def export_csv(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Download raw normalized cost lines for the filtered range as CSV."""
    # Fetch plain tuples now: the DB session is closed before the streamed body is sent.
    cols = (CostRecord.usage_date, CostRecord.provider, CostRecord.account_id, CostRecord.service, CostRecord.resource_type,
            CostRecord.environment, CostRecord.region, CostRecord.resource_id, CostRecord.cost_usd, CostRecord.cost_original,
            CostRecord.currency_original)
    rows = db.execute(select(*cols).where(_cost_where(f)).order_by(CostRecord.usage_date, CostRecord.provider)).all()

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "provider", "account", "service", "resource_type", "environment", "region", "resource_id", "cost_usd", "cost_original", "currency"])
        yield buf.getvalue()
        for i in range(0, len(rows), 500):
            buf.seek(0)
            buf.truncate()
            for r in rows[i : i + 500]:
                w.writerow([*r[:8], f"{float(r[8]):.4f}", f"{float(r[9]):.4f}", r[10]])
            yield buf.getvalue()

    name = f"cloudlens_costs_{f.start}_{f.end}.csv"
    return StreamingResponse(generate(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
