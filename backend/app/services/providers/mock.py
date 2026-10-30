"""Deterministic mock data generator.

Produces realistic, repeatable cost, inventory and utilization data for AWS, Azure and GCP so
the whole platform (dashboard, trends, alerts) works without any cloud credentials.

Determinism: every value is derived from a hash of (resource, date/hour), so re-running a sync
for the same day returns the same numbers and the database upsert stays idempotent.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.services.providers.base import CloudProvider, CostItem, MetricItem, ResourceItem


def _rnd(*parts: object) -> float:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


@dataclass(frozen=True)
class MockAsset:
    name: str
    rtype: str
    service: str
    env: str
    region: str
    sku: str
    daily_usd: float
    cpu: Optional[float] = None  # mean CPU %
    mem: Optional[float] = None
    storage: Optional[float] = None
    billable_resource: bool = True  # False = account-level charge (support, data transfer)
    peak_amp: float = 12.0  # business-hours CPU swing


ACCOUNTS = {
    "aws": "123456789012",
    "azure": "8f2c6b1e-4d3a-4c55-9a1e-2b7f0c9d1a42",
    "gcp": "cloudlens-demo-prod",
}

CATALOG: Dict[str, List[MockAsset]] = {
    "aws": [
        MockAsset("prod-eks-cluster-01", "containers", "Amazon Elastic Kubernetes Service", "production", "ap-south-1", "m6i.2xlarge x6", 420, 72, 76, peak_amp=14),
        MockAsset("web-asg-m5-xlarge", "compute", "Amazon Elastic Compute Cloud - Compute", "production", "ap-south-1", "m5.xlarge x4", 210, 58, 64),
        MockAsset("orders-rds-postgres", "database", "Amazon Relational Database Service", "production", "ap-south-1", "db.r6g.xlarge", 180, 46, 70),
        MockAsset("elasticache-sessions", "database", "Amazon ElastiCache", "production", "ap-south-1", "cache.r6g.large", 55, 35, 61),
        MockAsset("prod-nat-gateway", "networking", "Amazon Virtual Private Cloud", "production", "ap-south-1", "NAT Gateway", 65),
        MockAsset("s3-media-assets", "storage", "Amazon Simple Storage Service", "production", "ap-south-1", "S3 Standard", 95, storage=71),
        MockAsset("s3-log-archive", "storage", "Amazon Simple Storage Service", "development", "ap-south-1", "S3 Standard", 52, storage=14),
        MockAsset("staging-ec2-app", "compute", "Amazon Elastic Compute Cloud - Compute", "staging", "ap-south-1", "t3.large x2", 48, 18, 34),
        MockAsset("dev-jenkins-ec2", "compute", "Amazon Elastic Compute Cloud - Compute", "development", "ap-south-1", "c5.2xlarge", 36, 6, 22, peak_amp=3),
        MockAsset("lambda-image-resize", "compute", "AWS Lambda", "production", "ap-south-1", "Lambda", 18),
        MockAsset("aws-data-transfer", "networking", "AWS Data Transfer", "production", "global", "", 90, billable_resource=False),
        MockAsset("aws-support", "other", "AWS Support (Business)", "unassigned", "global", "", 45, billable_resource=False),
        MockAsset("aws-cloudwatch", "other", "AmazonCloudWatch", "production", "ap-south-1", "", 30, billable_resource=False),
    ],
    "azure": [
        MockAsset("prod-aks-cluster", "containers", "Azure Kubernetes Service", "production", "centralindia", "Standard_D8s_v5 x4", 230, 66, 72),
        MockAsset("payments-sql-primary", "database", "SQL Database", "production", "centralindia", "BC_Gen5_8", 205, 63, 69),
        MockAsset("web-app-service-plan", "compute", "Azure App Service", "production", "centralindia", "P2v3 x3", 95, 52, 58),
        MockAsset("cosmos-catalog", "database", "Azure Cosmos DB", "production", "centralindia", "4000 RU/s", 70, 40, 45),
        MockAsset("media-blob-hot", "storage", "Storage", "production", "southindia", "Hot LRS", 88, storage=58),
        MockAsset("staging-aks-pool", "containers", "Azure Kubernetes Service", "staging", "centralindia", "Standard_D4s_v5 x3", 66, 23, 38),
        MockAsset("dev-vm-build-agent", "compute", "Virtual Machines", "development", "centralindia", "Standard_D4s_v5", 32, 9, 25, peak_amp=4),
        MockAsset("app-gateway-waf", "networking", "Application Gateway", "production", "centralindia", "WAF_v2", 48),
        MockAsset("azure-bandwidth", "networking", "Bandwidth", "production", "global", "", 35, billable_resource=False),
        MockAsset("azure-monitor", "other", "Azure Monitor", "production", "centralindia", "", 22, billable_resource=False),
        MockAsset("azure-defender", "other", "Microsoft Defender for Cloud", "unassigned", "global", "", 18, billable_resource=False),
    ],
    "gcp": [
        MockAsset("gke-prod-cluster", "containers", "Kubernetes Engine", "production", "asia-south1", "e2-standard-8 x3", 135, 61, 67),
        MockAsset("analytics-bigquery", "database", "BigQuery", "production", "asia-south1", "On-demand", 120),
        MockAsset("ml-training-a100-vm", "compute", "Compute Engine", "development", "us-central1", "a2-highgpu-1g", 105, 7, 18, peak_amp=3),
        MockAsset("cloudsql-reporting", "database", "Cloud SQL", "staging", "asia-south1", "db-custom-4-16384", 42, 21, 44),
        MockAsset("gcs-data-lake", "storage", "Cloud Storage", "production", "asia-south1", "Standard", 55, storage=66),
        MockAsset("api-cloud-run", "containers", "Cloud Run", "production", "asia-south1", "Cloud Run", 28),
        MockAsset("gke-dev-cluster", "containers", "Kubernetes Engine", "development", "asia-south1", "e2-standard-4 x2", 30, 12, 30, peak_amp=5),
        MockAsset("gcp-networking", "networking", "Networking", "production", "global", "", 26, billable_resource=False),
        MockAsset("gcp-logging", "other", "Cloud Logging", "production", "asia-south1", "", 12, billable_resource=False),
    ],
}

# Built-in anomalies: on these weekday-independent cycles a resource's cost spikes.
# (provider, asset name, cycle length in days, offset, multiplier)
ANOMALY_CYCLES = [
    ("aws", "prod-eks-cluster-01", 23, 4, 2.8),
    ("azure", "payments-sql-primary", 31, 11, 3.0),
    ("gcp", "analytics-bigquery", 19, 6, 3.2),
]
GROWTH_REFERENCE = date(2026, 1, 1)
DISPLAY = {"aws": "Amazon Web Services", "azure": "Microsoft Azure", "gcp": "Google Cloud"}


def _resource_id(provider: str, asset: MockAsset) -> str:
    acct = ACCOUNTS[provider]
    if provider == "aws":
        return f"arn:aws:mock:{asset.region}:{acct}:{asset.name}"
    if provider == "azure":
        return f"/subscriptions/{acct}/resourceGroups/rg-{asset.env}/providers/Mock/{asset.name}"
    return f"//mock.googleapis.com/projects/{acct}/{asset.region}/{asset.name}"


class MockProvider(CloudProvider):
    """One instance per cloud (aws / azure / gcp)."""

    def __init__(self, provider: str, overrides: Optional[List[dict]] = None, now: Optional[datetime] = None):
        super().__init__()
        self.name = provider
        self.display_name = DISPLAY[provider] + " (mock)"
        self.assets = CATALOG[provider]
        self.overrides = overrides or []  # [{"provider","date","factor"}] injected anomalies for demos
        self._now = now
        self.tz = ZoneInfo(get_settings().TIMEZONE)

    # -- helpers ---------------------------------------------------------
    def now(self) -> datetime:
        return self._now or datetime.now(timezone.utc)

    def is_configured(self) -> bool:
        return True

    def account_id(self) -> str:
        return ACCOUNTS[self.name]

    def _daily_cost(self, asset: MockAsset, d: date) -> float:
        growth = 1 + 0.0009 * (d - GROWTH_REFERENCE).days
        noise = 1 + 0.12 * (_rnd(self.name, asset.name, d.isoformat()) - 0.5)
        weekly = 1.0
        if asset.rtype in ("compute", "containers") and d.weekday() >= 5:
            weekly = 0.88
        if asset.env == "development" and d.weekday() >= 5:
            weekly *= 0.92
        value = asset.daily_usd * growth * noise * weekly
        for prov, name, cycle, offset, mult in ANOMALY_CYCLES:
            if prov == self.name and name == asset.name and d.toordinal() % cycle == offset:
                value *= mult
        for ov in self.overrides:
            if ov.get("provider") == self.name and ov.get("date") == d.isoformat():
                if ov.get("asset") in (None, "", asset.name) and asset.billable_resource:
                    value *= float(ov.get("factor", 1))
        return value

    # -- interface -------------------------------------------------------
    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        today_local = self.now().astimezone(self.tz).date()
        items: List[CostItem] = []
        d = start
        while d < end:
            if d > today_local:
                break
            fraction = 1.0
            if d == today_local:
                local = self.now().astimezone(self.tz)
                fraction = max(0.02, (local.hour * 60 + local.minute) / 1440)
            for a in self.assets:
                cost = round(self._daily_cost(a, d) * fraction, 4)
                items.append(
                    CostItem(
                        provider=self.name,
                        account_id=self.account_id(),
                        usage_date=d,
                        service=a.service,
                        resource_type=a.rtype,
                        environment=a.env,
                        region=a.region,
                        resource_id=_resource_id(self.name, a) if a.billable_resource else "",
                        cost_usd=cost,
                        cost_original=cost,
                        currency_original="USD",
                        usage_quantity=round(24 * fraction, 2),
                        usage_unit="Hrs",
                    )
                )
            d += timedelta(days=1)
        self.api_calls += 1
        return items

    def fetch_resources(self) -> List[ResourceItem]:
        self.api_calls += 1
        return [
            ResourceItem(
                provider=self.name,
                account_id=self.account_id(),
                resource_id=_resource_id(self.name, a),
                name=a.name,
                resource_type=a.rtype,
                service=a.service,
                environment=a.env,
                region=a.region,
                sku=a.sku,
                status="running",
                tags={get_settings().ENV_TAG_KEY: a.env, "owner": "devops", "managed-by": "terraform"},
            )
            for a in self.assets
            if a.billable_resource
        ]

    def _sample(self, a: MockAsset, ts: datetime) -> MetricItem:
        local = ts.astimezone(self.tz)
        hour = local.hour + local.minute / 60
        # business-hours curve peaking ~15:00 local time, lower at weekends
        curve = math.sin((hour - 9) / 24 * 2 * math.pi)
        weekend = 0.75 if local.weekday() >= 5 else 1.0
        key = ts.strftime("%Y%m%d%H%M")
        cpu = mem = stor = None
        if a.cpu is not None:
            cpu = a.cpu * weekend + a.peak_amp * curve + 8 * (_rnd(a.name, "cpu", key) - 0.5)
            cpu = round(min(99.0, max(0.5, cpu)), 2)
        if a.mem is not None:
            mem = a.mem + 4 * curve + 4 * (_rnd(a.name, "mem", key) - 0.5)
            mem = round(min(99.0, max(1.0, mem)), 2)
        if a.storage is not None:
            days = (local.date() - GROWTH_REFERENCE).days
            stor = round(min(99.0, a.storage + 0.02 * days + 0.5 * (_rnd(a.name, "st", key) - 0.5)), 2)
        net_base = a.daily_usd / 10
        return MetricItem(
            provider=self.name,
            resource_id=_resource_id(self.name, a),
            ts=ts,
            cpu_percent=cpu,
            memory_percent=mem,
            storage_percent=stor,
            network_in_mb=round(net_base * (1 + curve * 0.4) * (0.8 + 0.4 * _rnd(a.name, "ni", key)), 2),
            network_out_mb=round(net_base * 0.6 * (1 + curve * 0.4) * (0.8 + 0.4 * _rnd(a.name, "no", key)), 2),
        )

    def fetch_metrics(self, resources: List[ResourceItem], start: datetime, end: datetime, step_minutes: int = 60) -> List[MetricItem]:
        wanted = {r.resource_id for r in resources}
        assets = [a for a in self.assets if a.billable_resource and _resource_id(self.name, a) in wanted]
        out: List[MetricItem] = []
        step = timedelta(minutes=step_minutes)
        # align to the step boundary so samples are stable across runs
        ts = start.replace(second=0, microsecond=0)
        ts -= timedelta(minutes=ts.minute % step_minutes)
        while ts <= end:
            for a in assets:
                if a.cpu is None and a.mem is None and a.storage is None:
                    continue
                out.append(self._sample(a, ts))
            ts += step
        self.api_calls += 1
        return out

    def test_connection(self) -> Dict[str, object]:
        return {"ok": True, "message": "Mock data generator active (DATA_SOURCE=mock)", "account": self.account_id()}
