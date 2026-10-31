# Module: Cloud Provider Connectors

**Path:** `backend/app/services/providers/`

## Interface (`base.py`)

```python
class CloudProvider(ABC):
    name: str; display_name: str; api_calls: int     # api_calls counted for cost visibility
    def is_configured(self) -> bool
    def account_id(self) -> str
    def fetch_costs(self, start: date, end: date) -> list[CostItem]          # start <= day < end
    def fetch_resources(self) -> list[ResourceItem]
    def fetch_metrics(self, resources, start: datetime, end: datetime, step_minutes=60) -> list[MetricItem]
    def test_connection(self) -> dict                                       # {"ok", "message", "account"}
```

The DTOs `CostItem`, `ResourceItem` and `MetricItem` are the unified format. `ProviderNotConfigured`
signals missing credentials; ingestion records it as a *skipped* run.

## Factory (`__init__.py`)

`connectors_for(name, db)` reads the cloud's mode (`services/cloud_accounts.py`). In Mock mode it returns one `MockProvider`, with the
INR exchange rate from Settings and any injected anomalies. In Live mode it returns one live connector per saved connection.
`get_connectors(db)` returns those for all `ENABLED_PROVIDERS`, and each one gets its own `sync_runs` row.
`build_live_provider(name, inr, config)` builds a connector from any config, which is how the form tests unsaved values.
Every connector has a `source` (`mock` or `live`) and, when live, an `environment`; both are stored on the rows it produces, and the
environment replaces whatever tags say.
`test_connection()` runs one check per permission through `CloudProvider.run_checks` and returns
`{ok, message, account, checks: [{name, ok, detail}]}`, with a plain-language `hint` for known failures and secrets removed.

## Mock (`mock.py`)

- `CATALOG`: 29 assets (13 AWS, 11 Azure, 9 GCP), of which 25 are billable resources. Each has a type,
  service, environment, region, SKU, base daily cost, mean CPU/memory/storage and an amplitude for daily peaks.
- **Deterministic:** values come from `sha256(resource, date)`, so re-syncing gives identical numbers.
- Cost model: base × growth (+0.09 %/day) × noise (±6 %) × weekend factor × built-in anomaly cycles
  (`ANOMALY_CYCLES`) × admin-injected overrides.
- Today's cost is pro-rated by the time of day (real-time view). Future dates return nothing.
- Metrics: a business-hours sine curve peaking about 15:00 IST, lower at weekends, plus noise; storage
  grows slowly over time.
- Built-in waste for the recommendations demo: `ml-training-a100-vm` (7 % CPU), `dev-jenkins-ec2`,
  `dev-vm-build-agent`, `s3-log-archive` (14 % used), and under-used staging clusters.

## AWS (`aws.py`)

| Data | API | Notes |
|---|---|---|
| Costs | `ce.get_cost_and_usage` | DAILY, `UnblendedCost` + `UsageQuantity`, GroupBy SERVICE, filtered to this account (`LINKED_ACCOUNT`), follows `NextPageToken` |
| Inventory | `ec2.describe_instances`, `rds.describe_db_instances` | Per region in the connection's *Regions to scan*; RDS ids are ARNs because identifiers repeat across accounts; `Name` tag becomes the display name |
| Metrics | `cloudwatch.get_metric_data` | CPUUtilization Average, up to 400 queries per call |
| Identity | `sts.get_caller_identity` | Cached account id |

Credentials: access keys or the EC2 instance role, chosen in the form.
`parse_cost_explorer(pages, account, inr_rate)` is pure and unit-tested; a Stubber test covers pagination.

## Azure (`azure.py`)

| Data | API | Notes |
|---|---|---|
| Costs | `CostManagementClient.query.usage` | ActualCost, Daily, grouped by ServiceName, ResourceLocation, TagKey; **7-day windows** stay under the 1000-row page size |
| Inventory | `ResourceManagementClient.resources.list` | Types mapped by the connection's settings |
| Metrics | `MonitorManagementClient.metrics.list` | Metric name per type (Percentage CPU, node_cpu_usage_percentage, cpu_percent, CpuPercentage) |

`parse_cost_query` handles column order by name; `_merge_duplicates` sums rows with the same key.
INR is converted to USD.

## GCP (`gcp.py`)

| Data | API | Notes |
|---|---|---|
| Costs | BigQuery query on the **billing export** table (`BILLING_SQL`) | Net cost = cost + credits; filters `_PARTITIONTIME`; `maximum_bytes_billed` 2 GB |
| Billing check | Cloud Billing API `get_project_billing_info` | Used by Test connection |
| Inventory + metrics | Cloud Monitoring `instance/cpu/utilization` | One call returns both the instances and their CPU series (×100 → %) |

## Adding a provider

See *How to add a new cloud provider* in [future-enhancements.md](../future-enhancements.md).
