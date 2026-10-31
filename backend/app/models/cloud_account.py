from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import utcnow


class CloudAccount(Base):
    """The data mode selected for one cloud on the Cloud Accounts screen."""

    __tablename__ = "cloud_accounts"

    provider: Mapped[str] = mapped_column(String(10), primary_key=True)  # aws | azure | gcp
    mode: Mapped[str] = mapped_column(String(10), default="mock")  # mock | live
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CloudConnection(Base):
    """A Live connection: one cloud account serving one environment of one cloud."""

    __tablename__ = "cloud_connections"

    provider: Mapped[str] = mapped_column(String(10), primary_key=True)
    environment: Mapped[str] = mapped_column(String(20), primary_key=True)  # production | staging | development
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # non-secret fields only
    secrets_encrypted: Mapped[str] = mapped_column(Text, default="")  # Fernet token, see core/crypto.py
    tested_hash: Mapped[str] = mapped_column(String(64), default="")  # last config that passed a test
    verified_hash: Mapped[str] = mapped_column(String(64), default="")  # saved config that passed a test
    account: Mapped[str] = mapped_column(String(80), default="")  # set when saved; rows of other accounts are not shown
    last_test_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_message: Mapped[str] = mapped_column(Text, default="")
    last_test_account: Mapped[str] = mapped_column(String(80), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
