"""Common provider interface and the unified data transfer objects every connector returns."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class CostItem:
    provider: str
    account_id: str
    usage_date: date
    service: str
    resource_type: str
    environment: str
    region: str
    cost_usd: float
    cost_original: float
    currency_original: str = "USD"
    resource_id: str = ""
    usage_quantity: float = 0.0
    usage_unit: str = ""


@dataclass
class ResourceItem:
    provider: str
    account_id: str
    resource_id: str
    name: str
    resource_type: str
    service: str
    environment: str
    region: str
    sku: str = ""
    status: str = "running"
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricItem:
    provider: str
    resource_id: str
    ts: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    storage_percent: Optional[float] = None
    network_in_mb: Optional[float] = None
    network_out_mb: Optional[float] = None


class ProviderNotConfigured(Exception):
    """Raised when live mode is selected but credentials are missing."""


class CloudProvider(ABC):
    name: str = ""
    display_name: str = ""

    def __init__(self) -> None:
        self.api_calls = 0  # counted so the UI can show API usage (Cost Explorer is billed per request)

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def account_id(self) -> str: ...

    @abstractmethod
    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        """Daily costs for start <= day < end."""

    @abstractmethod
    def fetch_resources(self) -> List[ResourceItem]: ...

    @abstractmethod
    def fetch_metrics(self, resources: List[ResourceItem], start: datetime, end: datetime) -> List[MetricItem]: ...

    def test_connection(self) -> Dict[str, object]:
        """Lightweight credential check used by the Cloud Accounts screen."""
        if not self.is_configured():
            return {"ok": False, "message": "Credentials not configured in .env"}
        try:
            return {"ok": True, "message": f"Connected to {self.display_name}", "account": self.account_id()}
        except Exception as exc:  # pragma: no cover - network dependent
            return {"ok": False, "message": str(exc)}
