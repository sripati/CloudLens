"""Runtime settings stored in the `app_settings` table (editable from the Settings screen)."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import CredentialsUnreadable, decrypt_secrets, encrypt_secrets
from app.models import AppSetting


log = logging.getLogger("cloudlens.settings")
WEBHOOKS_KEY = "webhooks_encrypted"


def defaults() -> Dict[str, Any]:
    s = get_settings()
    budget = s.DEFAULT_MONTHLY_BUDGET_USD
    return {
        "monthly_budget_usd": budget,
        "provider_budgets_usd": {"aws": round(budget * 0.48, 2), "azure": round(budget * 0.32, 2), "gcp": round(budget * 0.20, 2)},
        "exchange_rate_inr": s.DEFAULT_EXCHANGE_RATE_INR,
        "default_currency": "USD",
        "notification_channel": s.DEFAULT_NOTIFICATION_CHANNEL,
        "idle_cpu_threshold": 10.0,
        "underutilized_cpu_threshold": 30.0,
        "mock_anomalies": [],
    }


EDITABLE_KEYS = {
    "monthly_budget_usd", "provider_budgets_usd", "exchange_rate_inr", "default_currency",
    "notification_channel", "idle_cpu_threshold", "underutilized_cpu_threshold",
}


def get_value(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    if row is not None:
        return row.value
    return defaults().get(key)


def get_all(db: Session) -> Dict[str, Any]:
    values = defaults()
    for row in db.query(AppSetting).all():
        values[row.key] = row.value
    return values


def set_value(db: Session, key: str, value: Any, commit: bool = True) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    if commit:
        db.commit()


def budget_for(db: Session, provider: str | None) -> float:
    if provider:
        budgets = get_value(db, "provider_budgets_usd") or {}
        if provider in budgets:
            return float(budgets[provider])
    return float(get_value(db, "monthly_budget_usd"))


# ---------------------------------------------------------------- Slack / Teams webhooks
def _saved_webhooks(db: Session) -> Dict[str, str]:
    return decrypt_secrets(get_value(db, WEBHOOKS_KEY) or "")


def webhook_status(db: Session) -> Dict[str, Any]:
    """Which webhooks are saved. URLs are secrets, so only this summary leaves the server."""
    try:
        saved, unreadable = _saved_webhooks(db), False
    except CredentialsUnreadable:
        saved, unreadable = {}, True
    return {"slack_saved": bool(saved.get("slack")), "teams_saved": bool(saved.get("teams")), "unreadable": unreadable}


def webhook_urls(db: Session) -> Dict[str, str]:
    """URLs to deliver to: saved ones, else the bundled test inbox. Empty when the saved ones cannot be
    decrypted, so delivery fails visibly instead of quietly going to the test inbox."""
    s = get_settings()
    try:
        saved = _saved_webhooks(db)
    except CredentialsUnreadable:
        log.error("saved webhook URLs cannot be decrypted; enter them again in Settings")
        return {"slack": "", "teams": ""}
    return {"slack": saved.get("slack") or s.SLACK_WEBHOOK_URL, "teams": saved.get("teams") or s.TEAMS_WEBHOOK_URL}


def save_webhooks(db: Session, slack: str | None, teams: str | None) -> None:
    """None keeps the saved URL, an empty string removes it."""
    try:
        saved = _saved_webhooks(db)
    except CredentialsUnreadable:
        saved = {}
    for channel, url in (("slack", slack), ("teams", teams)):
        if url is not None:
            saved[channel] = url
    set_value(db, WEBHOOKS_KEY, encrypt_secrets({k: v for k, v in saved.items() if v}), commit=False)


def publish_alertmanager_slack_url(db: Session) -> None:
    """Alertmanager sends "backend is down" alerts straight to Slack, so it cannot ask the backend for
    the URL. It reads this file (api_url_file) each time it sends."""
    folder = get_settings().ALERTMANAGER_SHARED_DIR
    if not os.path.isdir(folder):
        return  # running without Docker: no Alertmanager to serve
    path = os.path.join(folder, "slack_webhook_url")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(webhook_urls(db)["slack"])
    os.replace(tmp, path)
