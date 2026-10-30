# Database Design (PostgreSQL 16)

Tables are created by SQLAlchemy on startup (`init_db()` → `Base.metadata.create_all`).
Models live in `backend/app/models/`.

## Entity-relationship diagram

```mermaid
erDiagram
    users ||--o{ alert_rules : "created_by"
    alert_rules ||--o{ alert_events : "rule_id"
    resources ||--o{ resource_metrics : "resource_pk"
    resources ||..o{ cost_records : "resource_id (logical)"

    users {
        int id PK
        string email UK
        string full_name
        string hashed_password
        string role "admin | viewer"
        bool is_active
        timestamptz created_at
        timestamptz last_login_at
    }
    cost_records {
        int id PK
        string provider "aws | azure | gcp"
        string account_id
        date usage_date
        string service
        string resource_type
        string environment
        string region
        string resource_id
        numeric cost_usd
        numeric cost_original
        string currency_original
        float usage_quantity
        string usage_unit
        string source "mock | live"
        timestamptz ingested_at
    }
    resources {
        int id PK
        string provider
        string account_id
        string resource_id
        string name
        string resource_type
        string service
        string environment
        string region
        string sku
        string status
        json tags
        timestamptz first_seen_at
        timestamptz last_seen_at
    }
    resource_metrics {
        int id PK
        int resource_pk FK
        timestamptz ts
        float cpu_percent
        float memory_percent
        float storage_percent
        float network_in_mb
        float network_out_mb
    }
    alert_rules {
        int id PK
        string name
        string metric
        string provider
        string environment
        string resource_type
        string operator
        float threshold
        string severity
        string channels
        bool enabled
        string state "ok | firing"
        float last_value
        text last_detail
        timestamptz last_evaluated_at
        int created_by FK
    }
    alert_events {
        int id PK
        int rule_id FK
        string fingerprint
        string status "firing | resolved"
        string severity
        string title
        text message
        json labels
        string source "alertmanager | direct | test"
        string notified_channels
        string notification_status
        bool acknowledged
        timestamptz created_at
    }
    sync_runs {
        int id PK
        string provider
        string job
        string data_source
        string status
        int cost_records
        int resources
        int metric_samples
        int api_calls
        text error
        timestamptz started_at
        timestamptz finished_at
    }
    app_settings {
        string key PK
        json value
        timestamptz updated_at
    }
```

## Unified cost schema (the heart of the system)

Every provider's billing data is converted into `cost_records` with **one grain**:

> provider + account + day + service + environment + region + resource

| Field | AWS source | Azure source | GCP source |
|---|---|---|---|
| `usage_date` | `TimePeriod.Start` | `UsageDate` (yyyymmdd) | `DATE(usage_start_time)` |
| `service` | `SERVICE` dimension | `ServiceName` | `service.description` |
| `environment` | tag group `environment$<v>` | `TagValue` of the env tag | label `environment` |
| `region` | `global` (CE groups by 2 keys max) | `ResourceLocation` | `location.region` |
| `cost_usd` | `UnblendedCost.Amount` | `Cost` (INR → USD) | `cost + credits` (export conversion rate) |

`resource_type` is derived from `service` by `services/normalizer.py`.

## Constraints and indexes

| Table | Constraint / index | Purpose |
|---|---|---|
| cost_records | `UNIQUE(provider, account_id, usage_date, service, environment, region, resource_id)` | Idempotent upserts: re-running a sync never duplicates |
| cost_records | `(provider, usage_date)`, `(environment, usage_date)`, `(resource_type, usage_date)`, `(usage_date)` | Fast filtered `GROUP BY` for trends |
| resources | `UNIQUE(provider, resource_id)` | Inventory upsert |
| resource_metrics | `UNIQUE(resource_pk, ts)`, index `(resource_pk, ts)` | Latest-sample and window queries |
| users | `UNIQUE(email)` | Login |

## Retention (cost optimization)

The daily `retention` job (03:30) deletes:

- `resource_metrics` older than `METRICS_RETENTION_DAYS` (90)
- `cost_records` older than `COST_RETENTION_DAYS` (730)
- `sync_runs` older than 60 days

With 3 providers, about 25 resources and hourly or 5-minute samples, the database stays well under 500 MB.

## Volume estimate (mock data)

| Table | Rows after 180-day backfill |
|---|---|
| cost_records | about 6,000 (≈ 33 / day) |
| resources | 25 |
| resource_metrics | about 3,400 initial, +about 550 / hour at 5-minute sampling |

## Backup and restore

```bash
./scripts/backup_db.sh                        # backups/cloudlens_<timestamp>.sql.gz (keeps 14)
./scripts/backup_db.sh restore backups/file.sql.gz
```

## Useful queries

```sql
-- Monthly cost per provider
SELECT date_trunc('month', usage_date) AS month, provider, round(sum(cost_usd), 2)
FROM cost_records GROUP BY 1, 2 ORDER BY 1, 2;

-- Top 10 services in the last 30 days
SELECT service, round(sum(cost_usd), 2) AS cost FROM cost_records
WHERE usage_date >= current_date - 30 GROUP BY service ORDER BY cost DESC LIMIT 10;

-- Latest CPU per resource
SELECT DISTINCT ON (r.name) r.name, m.ts, m.cpu_percent
FROM resource_metrics m JOIN resources r ON r.id = m.resource_pk
ORDER BY r.name, m.ts DESC;
```
