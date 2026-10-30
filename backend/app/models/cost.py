from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class CostRecord(Base):
    """One normalized daily cost line.

    Grain: provider + account + day + service + environment + region + resource.
    Every provider's raw billing data is converted into this unified shape
    (see app/services/normalizer.py) so the dashboard can compare clouds directly.
    """

    __tablename__ = "cost_records"
    __table_args__ = (
        UniqueConstraint(
            "provider", "account_id", "usage_date", "service", "environment", "region", "resource_id",
            name="uq_cost_record_grain",
        ),
        Index("ix_cost_provider_date", "provider", "usage_date"),
        Index("ix_cost_env_date", "environment", "usage_date"),
        Index("ix_cost_type_date", "resource_type", "usage_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(10))  # aws | azure | gcp
    account_id: Mapped[str] = mapped_column(String(80))
    usage_date: Mapped[date] = mapped_column(Date, index=True)
    service: Mapped[str] = mapped_column(String(120))  # provider-native service name
    resource_type: Mapped[str] = mapped_column(String(20))  # compute|containers|database|storage|networking|other
    environment: Mapped[str] = mapped_column(String(20))  # production|staging|development|unassigned
    region: Mapped[str] = mapped_column(String(40), default="global")
    resource_id: Mapped[str] = mapped_column(String(255), default="")  # '' when billing is not resource-level
    cost_usd: Mapped[float] = mapped_column(Numeric(14, 4))
    cost_original: Mapped[float] = mapped_column(Numeric(14, 4))
    currency_original: Mapped[str] = mapped_column(String(3), default="USD")
    usage_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    usage_unit: Mapped[str] = mapped_column(String(40), default="")
    source: Mapped[str] = mapped_column(String(10), default="mock")  # mock | live
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
