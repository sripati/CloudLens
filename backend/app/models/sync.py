from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class SyncRun(Base):
    """Audit log of every data fetch from a cloud provider."""

    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(10), index=True)
    job: Mapped[str] = mapped_column(String(20))  # backfill | daily | intraday | metrics | manual
    data_source: Mapped[str] = mapped_column(String(10))  # mock | live
    environment: Mapped[str] = mapped_column(String(20), default="")  # the Live connection's environment; empty for mock
    status: Mapped[str] = mapped_column(String(15), default="running")  # running | success | failed | skipped
    triggered_by: Mapped[str] = mapped_column(String(20), default="scheduler")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cost_records: Mapped[int] = mapped_column(Integer, default=0)
    resources: Mapped[int] = mapped_column(Integer, default=0)
    metric_samples: Mapped[int] = mapped_column(Integer, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
