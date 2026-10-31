"""Cloud Accounts: per-cloud Mock / Live mode and the per-environment connection form."""
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import SessionLocal, get_db
from app.models import User
from app.schemas import CloudConfigIn, CloudModeIn
from app.services import cloud_accounts, settings_service
from app.services.cloud_accounts import AccountInUse, ConfigNotVerified
from app.services.providers import build_live_provider

router = APIRouter(prefix="/cloud-accounts", tags=["cloud accounts"])
ENV_QUERY = Query("production", pattern="^(production|staging|development)$")


def _check(provider: str) -> None:
    if provider not in cloud_accounts.PROVIDERS:
        raise HTTPException(404, "Unknown provider")


def _reject_invalid(provider: str, cfg: dict) -> None:
    errors = cloud_accounts.validate(provider, cfg)
    if errors:
        raise HTTPException(422, [{"loc": ["config", e["field"]], "msg": e["message"]} for e in errors])


def _load_in_background(provider: str, environment: Optional[str] = None) -> None:
    """Bring the cloud's data up to date, without holding the request open."""
    def work():
        db = SessionLocal()
        try:
            from app.services.alert_engine import evaluate_all, refresh_metrics
            from app.services.ingestion import load_active

            load_active(db, provider, triggered_by="mode-change", environment=environment)
            evaluate_all(db)
            refresh_metrics(db)
        finally:
            db.close()

    threading.Thread(target=work, daemon=True).start()


@router.get("/{provider}")
def read_config(provider: str, environment: str = ENV_QUERY, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _check(provider)
    return cloud_accounts.public_view(db, provider, environment)


@router.post("/{provider}/test")
def test_config(provider: str, body: CloudConfigIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Validate the values in the form, then call the cloud APIs with them. Nothing is saved."""
    _check(provider)
    cfg = cloud_accounts.effective_config(db, provider, body.environment, body.config)
    _reject_invalid(provider, cfg)
    inr = float(settings_service.get_value(db, "exchange_rate_inr"))
    p = build_live_provider(provider, inr, cfg)
    result = p.test_connection()
    other = cloud_accounts.account_conflict(db, provider, body.environment, str(result.get("account") or "")) if result.get("ok") else None
    if other:
        message = f"Account {result['account']} is already configured for {other.title()}. Use a different account, or its cost would count twice."
        result = {"ok": False, "message": message, "checks": [*result.get("checks", []), {"name": "Account not already used", "ok": False, "detail": message}]}
    cloud_accounts.record_test(db, provider, body.environment, cfg, result)
    return {"provider": provider, "environment": body.environment, **result, "api_calls": p.api_calls}


@router.put("/{provider}/config")
def save_config(provider: str, body: CloudConfigIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _check(provider)
    _reject_invalid(provider, cloud_accounts.effective_config(db, provider, body.environment, body.config))
    try:
        cloud_accounts.save_config(db, provider, body.environment, body.config)
        was_mock = cloud_accounts.mode_of(db, provider) == "mock"
        if body.activate:
            cloud_accounts.set_mode(db, provider, "live")
    except (ConfigNotVerified, AccountInUse) as exc:
        raise HTTPException(409, str(exc))
    if body.activate and was_mock:
        _load_in_background(provider)  # every saved environment becomes active, not only this one
    elif cloud_accounts.mode_of(db, provider) == "live":
        _load_in_background(provider, body.environment)
    return cloud_accounts.public_view(db, provider, body.environment)


@router.put("/{provider}/mode")
def set_mode(provider: str, body: CloudModeIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _check(provider)
    changed = cloud_accounts.mode_of(db, provider) != body.mode
    try:
        cloud_accounts.set_mode(db, provider, body.mode)
    except ConfigNotVerified as exc:
        raise HTTPException(409, str(exc))
    if changed:
        _load_in_background(provider)
    return {"provider": provider, "mode": body.mode}


@router.delete("/{provider}/config")
def remove_config(provider: str, environment: str = ENV_QUERY, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    _check(provider)
    was_live = cloud_accounts.mode_of(db, provider) == "live"
    cloud_accounts.clear_config(db, provider, environment)
    if was_live and cloud_accounts.mode_of(db, provider) == "mock":
        _load_in_background(provider)
    return cloud_accounts.public_view(db, provider, environment)
