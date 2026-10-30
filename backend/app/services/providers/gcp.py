"""GCP connector.

* Costs     : Cloud Billing export in BigQuery (the Cloud Billing API exposes billing accounts and
              budgets but not daily cost lines, so Google's recommended source for cost data is the
              standard usage cost export table). Queries always filter on the partition column to
              keep BigQuery scan cost minimal.
* Billing   : Cloud Billing API (`CloudBillingClient`) to verify the project's billing account
* Inventory + metrics : Cloud Monitoring `compute.googleapis.com/instance/cpu/utilization`
              (one call returns both the instance list and its CPU series)

Authentication: service-account JSON key via GOOGLE_APPLICATION_CREDENTIALS with roles
"BigQuery Data Viewer", "BigQuery Job User", "Monitoring Viewer" and "Billing Account Viewer".
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from app.core.config import get_settings
from app.services.normalizer import classify_service, normalize_environment, normalize_region, to_usd
from app.services.providers.base import CloudProvider, CostItem, MetricItem, ProviderNotConfigured, ResourceItem

BILLING_SQL = """
SELECT
  DATE(usage_start_time, @tz) AS usage_date,
  project.id AS project_id,
  service.description AS service,
  IFNULL(location.region, 'global') AS region,
  (SELECT value FROM UNNEST(labels) WHERE key = @env_key LIMIT 1) AS env,
  currency,
  ANY_VALUE(currency_conversion_rate) AS conversion_rate,
  SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_cost,
  SUM(usage.amount_in_pricing_units) AS usage_qty,
  ANY_VALUE(usage.pricing_unit) AS usage_unit
FROM `{table}`
WHERE _PARTITIONTIME >= TIMESTAMP(DATE_SUB(@start, INTERVAL 1 DAY))
  AND DATE(usage_start_time, @tz) >= @start
  AND DATE(usage_start_time, @tz) < @end
GROUP BY usage_date, project_id, service, region, env, currency
"""


def parse_billing_rows(rows: Iterable[Dict[str, Any]], inr_rate: float, default_project: str) -> List[CostItem]:
    """Convert BigQuery billing-export rows into CostItems (pure, unit-tested)."""
    items: List[CostItem] = []
    for row in rows:
        cost = float(row.get("net_cost") or 0)
        if abs(cost) < 1e-9:
            continue
        currency = row.get("currency") or "USD"
        rate = row.get("conversion_rate")
        service = row.get("service") or "Unknown"
        day = row["usage_date"]
        if isinstance(day, str):
            day = date.fromisoformat(day)
        items.append(
            CostItem(
                provider="gcp",
                account_id=row.get("project_id") or default_project,
                usage_date=day,
                service=service,
                resource_type=classify_service(service),
                environment=normalize_environment(row.get("env")),
                region=normalize_region(row.get("region")),
                cost_usd=round(to_usd(cost, currency, inr_rate, rate if currency != "USD" else None), 4),
                cost_original=round(cost, 4),
                currency_original=currency[:3],
                usage_quantity=float(row.get("usage_qty") or 0),
                usage_unit=(row.get("usage_unit") or "")[:40],
            )
        )
    return items


class GCPProvider(CloudProvider):
    name = "gcp"
    display_name = "Google Cloud"

    def __init__(self, inr_rate: float = 84.2):
        super().__init__()
        self.s = get_settings()
        self.inr_rate = inr_rate

    def is_configured(self) -> bool:
        creds = self.s.GOOGLE_APPLICATION_CREDENTIALS
        return bool(self.s.GCP_PROJECT_ID and self.s.GCP_BILLING_EXPORT_TABLE and creds and os.path.exists(creds))

    def _check(self) -> None:
        if not self.is_configured():
            raise ProviderNotConfigured("GCP not configured (GOOGLE_APPLICATION_CREDENTIALS, GCP_PROJECT_ID, GCP_BILLING_EXPORT_TABLE)")

    def account_id(self) -> str:
        return self.s.GCP_PROJECT_ID

    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        self._check()
        from google.cloud import bigquery

        client = bigquery.Client(project=self.s.GCP_PROJECT_ID)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start", "DATE", start),
                bigquery.ScalarQueryParameter("end", "DATE", end),
                bigquery.ScalarQueryParameter("env_key", "STRING", self.s.ENV_TAG_KEY),
                bigquery.ScalarQueryParameter("tz", "STRING", self.s.TIMEZONE),
            ],
            maximum_bytes_billed=2 * 1024**3,  # guard rail: never scan more than 2 GB per sync
        )
        self.api_calls += 1
        rows = client.query(BILLING_SQL.format(table=self.s.GCP_BILLING_EXPORT_TABLE), job_config=job_config).result()
        return parse_billing_rows((dict(r.items()) for r in rows), self.inr_rate, self.account_id())

    def _cpu_series(self, start: datetime, end: datetime, step_minutes: int):
        self._check()
        from google.cloud import monitoring_v3

        client = monitoring_v3.MetricServiceClient()
        interval = monitoring_v3.TimeInterval(
            {"start_time": {"seconds": int(start.timestamp())}, "end_time": {"seconds": int(end.timestamp())}}
        )
        aggregation = monitoring_v3.Aggregation(
            {"alignment_period": {"seconds": step_minutes * 60}, "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN}
        )
        self.api_calls += 1
        return client.list_time_series(
            request={
                "name": f"projects/{self.s.GCP_PROJECT_ID}",
                "filter": 'metric.type = "compute.googleapis.com/instance/cpu/utilization"',
                "interval": interval,
                "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                "aggregation": aggregation,
            }
        )

    def fetch_resources(self) -> List[ResourceItem]:
        end = datetime.now(timezone.utc)
        out: Dict[str, ResourceItem] = {}
        for series in self._cpu_series(end - timedelta(minutes=30), end, 10):
            labels = dict(series.resource.labels)
            inst_id = labels.get("instance_id", "")
            user_labels = dict(series.metadata.user_labels) if series.metadata else {}
            name = series.metric.labels.get("instance_name", inst_id)
            out[inst_id] = ResourceItem(
                provider="gcp",
                account_id=self.account_id(),
                resource_id=inst_id,
                name=name,
                resource_type="containers" if name.startswith("gke-") else "compute",
                service="Kubernetes Engine" if name.startswith("gke-") else "Compute Engine",
                environment=normalize_environment(user_labels.get(self.s.ENV_TAG_KEY)),
                region=normalize_region(labels.get("zone", "")),
                tags=user_labels,
            )
        return list(out.values())

    def fetch_metrics(self, resources: List[ResourceItem], start: datetime, end: datetime, step_minutes: int = 60) -> List[MetricItem]:
        wanted = {r.resource_id for r in resources if r.provider == "gcp"}
        out: List[MetricItem] = []
        for series in self._cpu_series(start, end, step_minutes):
            inst_id = series.resource.labels.get("instance_id", "")
            if inst_id not in wanted:
                continue
            for p in series.points:
                ts = p.interval.end_time
                ts = ts if isinstance(ts, datetime) else datetime.fromtimestamp(ts.seconds, tz=timezone.utc)
                out.append(MetricItem(provider="gcp", resource_id=inst_id, ts=ts, cpu_percent=round(p.value.double_value * 100, 2)))
        return out

    def test_connection(self) -> Dict[str, object]:
        if not self.is_configured():
            return {"ok": False, "message": "GCP service account / billing export table not set in .env"}
        try:
            from google.cloud import billing_v1

            client = billing_v1.CloudBillingClient()
            self.api_calls += 1
            info = client.get_project_billing_info(name=f"projects/{self.s.GCP_PROJECT_ID}")
            return {
                "ok": bool(info.billing_enabled),
                "message": f"Billing account {info.billing_account_name or 'n/a'}",
                "account": self.account_id(),
            }
        except Exception as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
