"""Runtime settings stored in the `app_settings` table (editable from the Settings screen)."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting


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
