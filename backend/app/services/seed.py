"""First-run seed: default users and a starter set of alert rules."""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import AlertRule, User

log = logging.getLogger("cloudlens.seed")

DEFAULT_RULES = [
    dict(name="Monthly budget 80% used", metric="budget_used_pct", operator=">=", threshold=80, severity="warning",
         description="Month-to-date spend reached 80% of the monthly budget."),
    dict(name="Forecast exceeds monthly budget", metric="forecast_budget_pct", operator=">", threshold=100, severity="critical",
         description="Projected month-end spend is above the monthly budget."),
    dict(name="Daily cost anomaly (+40%)", metric="cost_anomaly_pct", operator=">", threshold=40, severity="critical",
         description="Yesterday's cost was more than 40% above the trailing 7-day average."),
    dict(name="Production CPU above 80%", metric="resource_cpu", operator=">", threshold=80, severity="warning", environment="production",
         description="A production resource is over-utilized."),
    dict(name="Idle resources detected", metric="idle_resource_count", operator=">", threshold=0, severity="info",
         description="Resources with average CPU below 10% for 7 days are wasting money."),
    dict(name="AWS daily spend above $1,800", metric="daily_cost", operator=">", threshold=1800, severity="warning", provider="aws",
         description="AWS cost for the last full day crossed $1,800."),
]


def seed(db: Session) -> None:
    s = get_settings()
    if not db.scalar(select(func.count()).select_from(User)):
        db.add_all([
            User(email=s.ADMIN_EMAIL.lower(), full_name=s.ADMIN_NAME, hashed_password=hash_password(s.ADMIN_PASSWORD), role="admin"),
            User(email=s.VIEWER_EMAIL.lower(), full_name=s.VIEWER_NAME, hashed_password=hash_password(s.VIEWER_PASSWORD), role="viewer"),
        ])
        log.info("created default users %s (admin) and %s (viewer)", s.ADMIN_EMAIL, s.VIEWER_EMAIL)
    if not db.scalar(select(func.count()).select_from(AlertRule)):
        db.add_all([AlertRule(**r) for r in DEFAULT_RULES])
        log.info("created %d default alert rules", len(DEFAULT_RULES))
    db.commit()
