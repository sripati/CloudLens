"""Provider factory: one mock connector per cloud in Mock mode, one live connector per saved connection in Live mode."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.providers.base import CloudProvider


def build_live_provider(name: str, inr: float, config: Optional[Dict[str, str]] = None) -> CloudProvider:
    if name == "aws":
        from app.services.providers.aws import AWSProvider

        return AWSProvider(inr_rate=inr, config=config)
    if name == "azure":
        from app.services.providers.azure import AzureProvider

        return AzureProvider(inr_rate=inr, config=config)
    if name == "gcp":
        from app.services.providers.gcp import GCPProvider

        return GCPProvider(inr_rate=inr, config=config)
    raise ValueError(f"Unknown provider {name}")


def connectors_for(name: str, db: Session) -> List[CloudProvider]:
    from app.services import cloud_accounts, settings_service

    if cloud_accounts.mode_of(db, name) == "mock":
        from app.services.providers.mock import MockProvider

        return [MockProvider(name, overrides=settings_service.get_value(db, "mock_anomalies") or [])]
    inr = float(settings_service.get_value(db, "exchange_rate_inr"))
    return [build_live_provider(name, inr, cloud_accounts.effective_config(db, name, conn.environment)) for conn in cloud_accounts.saved_connections(db, name)]


def get_connectors(db: Session) -> List[Tuple[str, CloudProvider]]:
    return [(name, c) for name in get_settings().enabled_providers for c in connectors_for(name, db)]
