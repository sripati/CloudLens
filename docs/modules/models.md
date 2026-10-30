# Module: Data Models

**Path:** `backend/app/models/`. Full ER diagram and indexes: [../database.md](../database.md).

| File | Model | Table | Notes |
|---|---|---|---|
| `user.py` | `User` | users | `role` = admin \| viewer; `utcnow()` helper used by all models |
| `cost.py` | `CostRecord` | cost_records | Unified daily cost line; unique natural key for upserts |
| `resource.py` | `Resource`, `ResourceMetric` | resources, resource_metrics | Inventory + utilization samples (cascade delete) |
| `alert.py` | `AlertRule`, `AlertEvent` | alert_rules, alert_events | Also defines `ALERT_METRICS`, `OPERATORS`, `SEVERITIES`, `CHANNELS` |
| `sync.py` | `SyncRun` | sync_runs | One row per provider per job; counts and API calls |
| `setting.py` | `AppSetting` | app_settings | JSON key/value (budget, rate, channel, thresholds, mock anomalies) |

`app/models/__init__.py` imports every model so `Base.metadata` knows all tables.

## Conventions

- Timestamps are `DateTime(timezone=True)` stored in UTC; day boundaries use `TIMEZONE` (IST) in the services.
- Money is stored as `Numeric(14, 4)` in **USD** (`cost_usd`) plus the original amount and currency.
- Enumerations are plain strings validated in Pydantic schemas, so new values need no DB migration.
- `resource_id` in `cost_records` is `''` (not NULL) for account-level charges, so the unique constraint works
  (NULLs never conflict in SQL).

## Adding a field

1. Add the `mapped_column` to the model.
2. On an existing database, add the column manually (`ALTER TABLE ...`) or through Alembic.
3. Expose it in the relevant schema in `app/schemas/__init__.py` and in the service output.
