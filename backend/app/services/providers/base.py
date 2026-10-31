"""Common provider interface and the unified data transfer objects every connector returns."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Dict, List, Optional, Tuple


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
    source: str = "live"  # stored on every row this connector produces

    def __init__(self) -> None:
        self.environment = ""  # the environment a Live connection serves; empty for mock
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

    def secret_values(self) -> List[str]:
        """Values that must never appear in an error shown to the user."""
        return []

    def hint(self, exc: Exception) -> str:
        """Plain-language next step for a failed connection check."""
        return ""

    def run_checks(self, steps: List[Tuple[str, Callable[[], str]]]) -> Dict[str, object]:
        """Run each permission check and report all of them, so one test shows everything to fix.

        Stops after the first step when it fails: that step is the login, and the rest would fail the same way.
        """
        checks: List[Dict[str, object]] = []
        for i, (label, step) in enumerate(steps):
            try:
                checks.append({"name": label, "ok": True, "detail": step()})
            except ImportError:
                checks.append({"name": label, "ok": False, "detail": "Cloud SDK not installed. Rebuild the backend with INSTALL_CLOUD_SDKS=true."})
            except Exception as exc:
                checks.append({"name": label, "ok": False, "detail": self._explain(exc)})
            if i == 0 and not checks[0]["ok"]:
                break
        failed = [c for c in checks if not c["ok"]]
        if failed:
            return {"ok": False, "message": f"{failed[0]['name']}: {failed[0]['detail']}", "checks": checks}
        return {"ok": True, "message": f"Connected to {self.display_name}", "account": self.account_id(), "checks": checks}

    def _explain(self, exc: Exception) -> str:
        text = f"{type(exc).__name__}: {exc}"[:600]
        for secret in self.secret_values():
            if secret:
                text = text.replace(secret, "***")
        tip = self.hint(exc)
        return f"{tip} ({text})" if tip else text

    def test_connection(self) -> Dict[str, object]:
        """Lightweight credential check used by the Cloud Accounts screen."""
        if not self.is_configured():
            return {"ok": False, "message": "Credentials not configured"}
        try:
            return {"ok": True, "message": f"Connected to {self.display_name}", "account": self.account_id()}
        except Exception as exc:  # pragma: no cover - network dependent
            return {"ok": False, "message": str(exc)}
