"""Azure connector.

* Costs     : Cost Management Query API (ActualCost, Daily, grouped by ServiceName and ResourceLocation)
* Inventory : Resource Management `resources.list` (VMs, AKS, SQL, Storage, gateways)
* Metrics   : Azure Monitor metrics ("Percentage CPU" for VMs, "node_cpu_usage_percentage" for AKS,
              "cpu_percent" for SQL databases)

Authentication: service principal (AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET) with the
"Cost Management Reader" and "Monitoring Reader" roles on the subscription.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.normalizer import classify_service, normalize_environment, normalize_region, to_usd
from app.services.providers.base import CloudProvider, CostItem, MetricItem, ProviderNotConfigured, ResourceItem

# Azure resource type -> (normalized type, display service, metric name or None)
AZURE_TYPES = {
    "microsoft.compute/virtualmachines": ("compute", "Virtual Machines", "Percentage CPU"),
    "microsoft.containerservice/managedclusters": ("containers", "Azure Kubernetes Service", "node_cpu_usage_percentage"),
    "microsoft.sql/servers/databases": ("database", "SQL Database", "cpu_percent"),
    "microsoft.documentdb/databaseaccounts": ("database", "Azure Cosmos DB", None),
    "microsoft.storage/storageaccounts": ("storage", "Storage", None),
    "microsoft.web/serverfarms": ("compute", "Azure App Service", "CpuPercentage"),
    "microsoft.network/applicationgateways": ("networking", "Application Gateway", None),
    "microsoft.network/loadbalancers": ("networking", "Load Balancer", None),
}


def parse_cost_query(result: Dict[str, Any], subscription: str, inr_rate: float) -> List[CostItem]:
    """Convert a Cost Management query result (dict form) into CostItems (pure, unit-tested)."""
    cols = [c["name"].lower() for c in result.get("columns", [])]
    idx = {name: i for i, name in enumerate(cols)}
    items: List[CostItem] = []
    for row in result.get("rows", []):
        cost = float(row[idx.get("cost", idx.get("pretaxcost", 0))] or 0)
        if cost == 0:
            continue
        raw_date = str(row[idx["usagedate"]])
        day = datetime.strptime(raw_date[:8], "%Y%m%d").date() if raw_date.isdigit() else date.fromisoformat(raw_date[:10])
        service = row[idx["servicename"]] if "servicename" in idx else "Unknown"
        region = row[idx["resourcelocation"]] if "resourcelocation" in idx else ""
        env = row[idx["tagvalue"]] if "tagvalue" in idx else None
        currency = row[idx["currency"]] if "currency" in idx else "USD"
        items.append(
            CostItem(
                provider="azure",
                account_id=subscription,
                usage_date=day,
                service=service or "Unknown",
                resource_type=classify_service(service or ""),
                environment=normalize_environment(env),
                region=normalize_region(region),
                cost_usd=round(to_usd(cost, currency, inr_rate), 4),
                cost_original=round(cost, 4),
                currency_original=(currency or "USD")[:3],
            )
        )
    return items


def _merge_duplicates(items: List[CostItem]) -> List[CostItem]:
    merged: Dict[tuple, CostItem] = {}
    for it in items:
        k = (it.usage_date, it.service, it.environment, it.region)
        if k in merged:
            merged[k].cost_usd = round(merged[k].cost_usd + it.cost_usd, 4)
            merged[k].cost_original = round(merged[k].cost_original + it.cost_original, 4)
        else:
            merged[k] = it
    return list(merged.values())


class AzureProvider(CloudProvider):
    name = "azure"
    display_name = "Microsoft Azure"

    def __init__(self, inr_rate: float = 84.2, config: Optional[Dict[str, str]] = None):
        super().__init__()
        self.c = config or {}
        self.environment = self.c.get("environment", "")
        self.inr_rate = inr_rate
        self._cred = None

    def is_configured(self) -> bool:
        c = self.c
        return all([c.get("tenant_id"), c.get("client_id"), c.get("client_secret"), c.get("subscription_id")])

    def secret_values(self) -> List[str]:
        return [self.c.get("client_secret", "")]

    def hint(self, exc: Exception) -> str:
        message = str(exc)
        if type(exc).__name__ == "ClientAuthenticationError" or "ClientSecretCredential.get_token failed" in message:
            return "Azure rejected this service principal. Check the tenant ID, client ID and client secret."
        if "AuthorizationFailed" in message or "does not have authorization" in message or "RBACAccessDenied" in message:
            return "The service principal lacks a role. Grant Cost Management Reader, Monitoring Reader and Reader on the subscription."
        if "SubscriptionNotFound" in message or "InvalidSubscriptionId" in message:
            return "Azure cannot find this subscription. Check the subscription ID."
        return ""

    def credential(self):
        if not self.is_configured():
            raise ProviderNotConfigured("Azure service principal not configured (AZURE_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SUBSCRIPTION_ID)")
        if self._cred is None:
            from azure.identity import ClientSecretCredential

            self._cred = ClientSecretCredential(self.c["tenant_id"], self.c["client_id"], self.c["client_secret"])
        return self._cred

    def account_id(self) -> str:
        return self.c["subscription_id"]

    @property
    def scope(self) -> str:
        return f"/subscriptions/{self.c['subscription_id']}"

    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import (
            GranularityType,
            QueryAggregation,
            QueryDataset,
            QueryDefinition,
            QueryGrouping,
            QueryTimePeriod,
        )

        client = CostManagementClient(self.credential())
        items: List[CostItem] = []
        # The Query API returns at most ~1000 rows per call; querying in 7-day windows keeps every
        # window well under that limit without needing to follow next_link pagination.
        window_start = start
        while window_start < end:
            window_end = min(end, window_start + timedelta(days=7))
            query = QueryDefinition(
                type="ActualCost",
                timeframe="Custom",
                time_period=QueryTimePeriod(
                    from_property=datetime.combine(window_start, datetime.min.time()),
                    to=datetime.combine(window_end - timedelta(days=1), datetime.max.time().replace(microsecond=0)),
                ),
                dataset=QueryDataset(
                    granularity=GranularityType.DAILY,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[
                        QueryGrouping(type="Dimension", name="ServiceName"),
                        QueryGrouping(type="Dimension", name="ResourceLocation"),
                    ],
                ),
            )
            self.api_calls += 1
            res = client.query.usage(scope=self.scope, parameters=query)
            result = {"columns": [{"name": c.name} for c in res.columns], "rows": list(res.rows)}
            items.extend(parse_cost_query(result, self.account_id(), self.inr_rate))
            window_start = window_end
        for item in items:
            item.environment = self.environment
        return _merge_duplicates(items)

    def fetch_resources(self) -> List[ResourceItem]:
        from azure.mgmt.resource import ResourceManagementClient

        client = ResourceManagementClient(self.credential(), self.c["subscription_id"])
        out: List[ResourceItem] = []
        self.api_calls += 1
        for res in client.resources.list():
            rtype = (res.type or "").lower()
            if rtype not in AZURE_TYPES:
                continue
            norm, service, _ = AZURE_TYPES[rtype]
            tags = dict(res.tags or {})
            out.append(
                ResourceItem(
                    provider="azure",
                    account_id=self.account_id(),
                    resource_id=res.id,
                    name=res.name,
                    resource_type=norm,
                    service=service,
                    environment=self.environment,
                    region=normalize_region(res.location),
                    sku=(res.sku.name if getattr(res, "sku", None) else "") or "",
                    status="running",
                    tags=tags,
                )
            )
        return out

    def fetch_metrics(self, resources: List[ResourceItem], start: datetime, end: datetime, step_minutes: int = 60) -> List[MetricItem]:
        from azure.mgmt.monitor import MonitorManagementClient

        client = MonitorManagementClient(self.credential(), self.c["subscription_id"])
        interval = "PT1H" if step_minutes >= 60 else "PT5M"
        timespan = f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        out: List[MetricItem] = []
        type_by_service = {v[1]: v[2] for v in AZURE_TYPES.values()}
        for r in resources:
            metric_name = type_by_service.get(r.service)
            if r.provider != "azure" or not metric_name:
                continue
            try:
                self.api_calls += 1
                data = client.metrics.list(r.resource_id, timespan=timespan, interval=interval, metricnames=metric_name, aggregation="Average")
            except Exception:
                continue
            for metric in data.value:
                for series in metric.timeseries:
                    for point in series.data:
                        if point.average is not None:
                            out.append(MetricItem(provider="azure", resource_id=r.resource_id, ts=point.time_stamp, cpu_percent=round(point.average, 2)))
        return out

    def _cost_query_one_day(self):
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.mgmt.costmanagement.models import GranularityType, QueryAggregation, QueryDataset, QueryDefinition, QueryTimePeriod

        day = datetime.now(timezone.utc).date() - timedelta(days=1)
        query = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=datetime.combine(day, datetime.min.time()), to=datetime.combine(day, datetime.max.time().replace(microsecond=0))),
            dataset=QueryDataset(granularity=GranularityType.DAILY, aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")}),
        )
        self.api_calls += 1
        return CostManagementClient(self.credential()).query.usage(scope=self.scope, parameters=query)

    def test_connection(self) -> Dict[str, object]:
        if not self.is_configured():
            return {"ok": False, "message": "Azure service principal not set"}

        def sign_in() -> str:
            self.api_calls += 1
            self.credential().get_token("https://management.azure.com/.default")
            return "Service principal accepted"

        def costs() -> str:
            self._cost_query_one_day()
            return "Cost data is readable"

        def inventory() -> str:
            from azure.mgmt.resource import ResourceManagementClient

            self.api_calls += 1
            next(iter(ResourceManagementClient(self.credential(), self.c["subscription_id"]).resources.list()), None)
            return "Resources readable"

        return self.run_checks([("Sign in (Entra ID)", sign_in), ("Cost Management", costs), ("Resource inventory", inventory)])
