from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.user import utcnow


class Resource(Base):
    """Inventory of cloud resources (VMs, clusters, databases, buckets, gateways...)."""

    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("provider", "resource_id", name="uq_resource_provider_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(10), index=True)
    account_id: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(255))  # native id / ARN / resource URI
    name: Mapped[str] = mapped_column(String(160))
    resource_type: Mapped[str] = mapped_column(String(20), index=True)
    service: Mapped[str] = mapped_column(String(120))
    environment: Mapped[str] = mapped_column(String(20), index=True)
    region: Mapped[str] = mapped_column(String(40), default="global")
    sku: Mapped[str] = mapped_column(String(80), default="")  # instance type / tier
    status: Mapped[str] = mapped_column(String(20), default="running")
    source: Mapped[str] = mapped_column(String(10), default="mock")  # mock | live
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    metrics = relationship("ResourceMetric", back_populates="resource", cascade="all, delete-orphan", lazy="noload")


class ResourceMetric(Base):
    """Utilization sample for a resource (hourly history + 5-minute near-real-time samples)."""

    __tablename__ = "resource_metrics"
    __table_args__ = (
        UniqueConstraint("resource_pk", "ts", name="uq_metric_resource_ts"),
        Index("ix_metric_resource_ts", "resource_pk", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_pk: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cpu_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    memory_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    storage_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    network_in_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    network_out_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    resource = relationship("Resource", back_populates="metrics")
