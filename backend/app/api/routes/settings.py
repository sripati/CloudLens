from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import User
from app.schemas import SettingsUpdate
from app.services import cloud_accounts, settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


def _public(db: Session) -> dict:
    s = get_settings()
    values = {k: v for k, v in settings_service.get_all(db).items() if k in settings_service.EDITABLE_KEYS}
    values["system"] = {
        "data_source": cloud_accounts.summary(db),
        "provider_modes": {p: cloud_accounts.mode_of(db, p) for p in s.enabled_providers},
        "alert_delivery": s.ALERT_DELIVERY,
        "enabled_providers": s.enabled_providers,
        "timezone": s.TIMEZONE,
        "webhooks": settings_service.webhook_status(db),
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
    values = body.model_dump(exclude_none=True)
    slack, teams = values.pop("slack_webhook_url", None), values.pop("teams_webhook_url", None)
    for key, value in values.items():
        settings_service.set_value(db, key, value, commit=False)
    if slack is not None or teams is not None:
        settings_service.save_webhooks(db, slack, teams)
    db.commit()
    settings_service.publish_alertmanager_slack_url(db)
    return _public(db)
