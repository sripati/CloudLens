"""Provider factory: returns mock or live connectors depending on DATA_SOURCE in .env."""
from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.providers.base import CloudProvider


def get_provider(name: str, db: Optional[Session] = None) -> CloudProvider:
    from app.services import settings_service

    s = get_settings()
    inr = float(settings_service.get_value(db, "exchange_rate_inr")) if db is not None else s.DEFAULT_EXCHANGE_RATE_INR
    if s.DATA_SOURCE == "mock":
        from app.services.providers.mock import MockProvider

        overrides = settings_service.get_value(db, "mock_anomalies") if db is not None else []
        return MockProvider(name, overrides=overrides or [])
    if name == "aws":
        from app.services.providers.aws import AWSProvider

        return AWSProvider(inr_rate=inr)
    if name == "azure":
        from app.services.providers.azure import AzureProvider

        return AzureProvider(inr_rate=inr)
    if name == "gcp":
        from app.services.providers.gcp import GCPProvider

        return GCPProvider(inr_rate=inr)
    raise ValueError(f"Unknown provider {name}")


def get_providers(db: Optional[Session] = None) -> Dict[str, CloudProvider]:
    return {name: get_provider(name, db) for name in get_settings().enabled_providers}
