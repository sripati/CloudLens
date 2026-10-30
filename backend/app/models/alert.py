from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow

# Metrics a rule can watch. Keep in sync with app/services/alert_engine.py and frontend Alerts screen.
ALERT_METRICS = {
    "daily_cost": "Daily cost of the last full day (USD)",
    "mtd_cost": "Month-to-date cost (USD)",
    "budget_used_pct": "Month-to-date cost as % of monthly budget",
    "forecast_budget_pct": "Month-end forecast as % of monthly budget",
    "cost_anomaly_pct": "Last full day vs trailing 7-day average (% change)",
    "resource_cpu": "Highest current CPU % of any resource in scope",
    "resource_memory": "Highest current memory % of any resource in scope",
    "idle_resource_count": "Number of resources with 7-day average CPU below 10%",
}
OPERATORS = {">", ">=", "<", "<="}
SEVERITIES = {"critical", "warning", "info"}
CHANNELS = {"default", "slack", "teams", "both"}


class AlertRule(Base):
    """User-defined alert criteria (created from the Alerts screen)."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    metric: Mapped[str] = mapped_column(String(40))
    provider: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # None = all
    environment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    operator: Mapped[str] = mapped_column(String(2), default=">")
    threshold: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10), default="warning")
    channels: Mapped[str] = mapped_column(String(10), default="default")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Runtime state written by the alert engine
    state: Mapped[str] = mapped_column(String(10), default="ok")  # ok | firing
    last_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_detail: Mapped[str] = mapped_column(Text, default="")
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AlertEvent(Base):
    """A notification-worthy alert occurrence (firing or resolved)."""

    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(10))  # firing | resolved
    severity: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, default="")
    value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    labels: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="alertmanager")  # alertmanager | direct | test
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_channels: Mapped[str] = mapped_column(String(40), default="")
    notification_status: Mapped[str] = mapped_column(String(20), default="pending")  # sent | failed | partial | skipped
    notification_error: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
