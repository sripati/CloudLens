# Module: Ingestion (Data Aggregation & Storage)

**Path:** `backend/app/services/ingestion.py`

## Responsibilities

1. Ask each provider for costs, inventory and metrics for a time window.
2. Store them idempotently in PostgreSQL.
3. Log every run (`sync_runs`) with counts, API calls and errors.
4. Apply data retention.

## Jobs (`run_job(db, job, triggered_by, providers)`)

| Job | Cost window | Metrics window | Used by |
|---|---|---|---|
| `backfill` | today − `BACKFILL_DAYS` … today | 7 days hourly | First start (`backfill_if_empty`); on later starts `extend_history` fetches only the older days missing after `BACKFILL_DAYS` was raised |
| `daily` | today − `SYNC_LOOKBACK_DAYS` … today | 26 h hourly | Scheduler 02:00 |
| `intraday` | today only | none | Scheduler, every `INTRADAY_COST_REFRESH_MINUTES` |
| `metrics` | none | last 2 × interval at `METRICS_INTERVAL_MINUTES` step | Scheduler, every 5 min |
| `manual` | lookback days | 2 h | *Sync now* buttons |

## Upserts

| Function | Conflict key | Behaviour |
|---|---|---|
| `upsert_costs` | provider, account, date, service, env, region, resource_id | Duplicates in the batch are first **summed**, then `ON CONFLICT DO UPDATE` (cost, currency, type, source) |
| `upsert_resources` | provider, resource_id | Updates name, type, env, sku, status, tags, last_seen; returns `{resource_id: pk}` |
| `upsert_metrics` | resource_pk, ts | Updates values |

Statements are built with the PostgreSQL or SQLite dialect `insert()` (both support `on_conflict_do_update`)
in chunks of 1000 rows.

## Error handling

`sync_provider` wraps each provider separately:
- `ProviderNotConfigured` → run `skipped` (normal in live mode for clouds you don't use)
- any other exception → `rollback`, run `failed` with `Type: message`; other providers continue
- The `cloudlens_sync_last_run_success` gauge drives the *CloudLensSyncFailing* Prometheus alert.

## Retention (`apply_retention`)

Deletes metrics older than `METRICS_RETENTION_DAYS`, costs older than `COST_RETENTION_DAYS`, and sync
logs older than 60 days. It runs daily at 03:30.

## Helpers

`local_today()` returns today's date in `TIMEZONE`, used everywhere a "day" boundary matters.
