from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import User
from app.schemas import SettingsUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


def _public(db: Session) -> dict:
    s = get_settings()
    values = {k: v for k, v in settings_service.get_all(db).items() if k in settings_service.EDITABLE_KEYS}
    values["system"] = {
        "data_source": s.DATA_SOURCE,
        "alert_delivery": s.ALERT_DELIVERY,
        "enabled_providers": s.enabled_providers,
        "timezone": s.TIMEZONE,
        "slack_configured": bool(s.SLACK_WEBHOOK_URL),
        "teams_configured": bool(s.TEAMS_WEBHOOK_URL),
        "slack_is_mock": "mock-receiver" in s.SLACK_WEBHOOK_URL or "localhost" in s.SLACK_WEBHOOK_URL,
        "teams_is_mock": "mock-receiver" in s.TEAMS_WEBHOOK_URL or "localhost" in s.TEAMS_WEBHOOK_URL,
        "metrics_interval_minutes": s.METRICS_INTERVAL_MINUTES,
        "intraday_cost_refresh_minutes": s.INTRADAY_COST_REFRESH_MINUTES,
        "daily_sync_time": f"{s.DAILY_SYNC_HOUR:02d}:{s.DAILY_SYNC_MINUTE:02d}",
        "metrics_retention_days": s.METRICS_RETENTION_DAYS,
        "app_env": s.APP_ENV,
    }
    return values


@router.get("")
def read_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _public(db)


@router.put("")
def update_settings(body: SettingsUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    for key, value in body.model_dump(exclude_none=True).items():
        settings_service.set_value(db, key, value, commit=False)
    db.commit()
    return _public(db)
