from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_filters
from app.core.database import get_db
from app.models import User
from app.schemas import AlertEventOut
from app.services import analytics
from app.services.analytics import Filters

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """KPI cards: period spend and change, month-to-date vs budget, forecast, alerts, savings."""
    return analytics.summary(db, f)


@router.get("/overview")
def overview(f: Filters = Depends(get_filters), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Everything the Dashboard screen needs in one round trip."""
    return {
        "summary": analytics.summary(db, f),
        "trend": analytics.daily_series(db, f, group_by="provider"),
        "by_provider": analytics.breakdown(db, f, "provider"),
        "by_resource_type": analytics.breakdown(db, f, "resource_type"),
        "by_environment": analytics.breakdown(db, f, "environment"),
        "utilization": analytics.utilization(db, f, hours=24 * 7),
        "top_resources": analytics.resources(db, f, limit=8),
        "anomalies": analytics.anomalies(db, f)[:10],
        "recent_alerts": [AlertEventOut.model_validate(e).model_dump(mode="json") for e in analytics.recent_events(db, 4)],
    }
