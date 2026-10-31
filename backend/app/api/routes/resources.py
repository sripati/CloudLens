from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_filters
from app.core.database import get_db
from app.models import User
from app.services import analytics
from app.services.analytics import Filters

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("")
def list_resources(
    search: str = Query("", max_length=100),
    status: str = Query("", pattern="^(|healthy|idle|over_utilized|no_metrics)$"),
    sort: str = Query("cost", pattern="^(cost|cpu|name)$"),
    limit: int = Query(200, le=1000),
    f: Filters = Depends(get_filters),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return analytics.resources(db, f, search=search, status=status, sort=sort, limit=limit)


@router.get("/utilization")
def utilization(hours: int = Query(168, ge=1, le=24 * 90), f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return analytics.utilization(db, f, hours)


@router.get("/recommendations")
def recommendations(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    recs = analytics.recommendations(db, f)
    return {"total_monthly_savings": round(sum(r["monthly_savings"] for r in recs), 2), "items": recs}


@router.get("/{resource_pk}")
def detail(resource_pk: int, f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Drill-down for one resource; cost covers start..end (or the last `days` days)."""
    data = analytics.resource_detail(db, resource_pk, f=f)
    if data is None:
        raise HTTPException(404, "Resource not found")
    return data
