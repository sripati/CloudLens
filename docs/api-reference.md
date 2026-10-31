# API Reference

Base path: `/api/v1`. Interactive docs: **`/docs`** (Swagger UI) and **`/redoc`**.
All endpoints except `/auth/login`, `/alerts/webhook`, `/health` and `/metrics` require
`Authorization: Bearer <JWT>`. 🔒 = admin role required.

## Common filter parameters

Accepted by dashboard, costs, resources and recommendations endpoints:

| Param | Example | Notes |
|---|---|---|
| `days` | `30` | Range of N days ending at `end` (default 30); used only when `start` is not given |
| `start`, `end` | `2026-09-01`, `2026-09-30` | Inclusive. `end` defaults to today. Validated (422 with a readable message): neither date in the future, `start` ≤ `end`, at most **731 days** |
| `provider` | `aws,gcp` | Comma separated; `all` or empty = no filter |
| `environment` | `production` | production, staging, development, unassigned |
| `resource_type` | `compute,database` | compute, containers, database, storage, networking, other |
| `service`, `region` | `BigQuery` | Exact match, comma separated |

Invalid values return **422** with a readable `detail`.

## Auth & users

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | `{email, password}` → `{access_token, expires_in, user}` |
| GET | `/auth/me` | Current user |
| POST | `/auth/change-password` | `{current_password, new_password}` → 204 |
| GET 🔒 | `/users` | List users |
| POST 🔒 | `/users` | `{email, full_name, password, role}` → 201, 409 if the email exists |
| PATCH 🔒 | `/users/{id}` | Update name, role, active flag or password (you cannot demote or disable yourself) |
| DELETE 🔒 | `/users/{id}` | Delete (not yourself) |

## Dashboard

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard/summary` | KPIs: period total and change, MTD, forecast, budget %, alert counts, savings, resource counts |
| GET | `/dashboard/overview` | Everything for the Dashboard screen in one call |

Example `summary` fields: `period_total`, `previous_period_total`, `period_change_pct`,
`month.{mtd, forecast, avg_daily_7d, last_month_total}`,
`budget.{budget, used_pct, forecast_pct, applies_to_filtered_view}`, `alerts.{critical, warning, info, total}`,
`savings.{monthly_total, count}`.

## Costs

| Method | Path | Description |
|---|---|---|
| GET | `/costs/daily?group_by=provider` | Zero-filled daily points `{date, total, ma7, <key>...}`. `group_by`: provider, environment, resource_type, service, region, account, none |
| GET | `/costs/breakdown?dimension=service` | Rows `{key, cost, pct, previous, change_pct}` vs the previous equal-length period |
| GET | `/costs/monthly?start=&end=` | One row per calendar month inside the range: totals per provider, `start`/`end`/`days_covered`, `partial` (month not fully covered, or still in progress), `change_pct` with `change_basis` = `total` (both months full) or `run_rate` (daily averages). Optional `months=N` = last N months ending at `end` |
| GET | `/costs/date-bounds` | `{today, min_date, max_date, max_range_days, timezone}`: what the date-range picker may offer (server timezone) |
| GET | `/costs/anomalies?threshold_pct=40` | Days where a provider exceeded its trailing 7-day average |
| GET | `/costs/filters` | Distinct providers, environments, types, services, regions, accounts |
| GET | `/costs/export` | CSV of normalized cost lines |

## Resources

| Method | Path | Description |
|---|---|---|
| GET | `/resources?search=&status=&sort=cost` | Inventory with cost, latest and 7-day CPU and memory, status (`healthy`, `idle`, `over_utilized`, `no_metrics`) |
| GET | `/resources/{id}?start=&end=` | Drill-down: details, tags, daily cost for the range (`period`), 7-day metrics, recommendations |
| GET | `/resources/utilization?hours=168` | Per-provider averages and peaks, current snapshot, CPU trend, counts |
| GET | `/resources/recommendations` | `{total_monthly_savings, items[]}` |

## Alerts

| Method | Path | Description |
|---|---|---|
| GET | `/alerts/metrics` | Catalog of watchable metrics with units |
| GET | `/alerts/rules` | Rules with live `state`, `last_value`, `last_detail` |
| POST 🔒 | `/alerts/rules` | Create (evaluated immediately) |
| PUT 🔒 | `/alerts/rules/{id}` | Update |
| DELETE 🔒 | `/alerts/rules/{id}` | Delete |
| POST 🔒 | `/alerts/evaluate` | Evaluate all rules now |
| GET | `/alerts/events?status=&severity=` | Notification history |
| POST | `/alerts/events/{id}/ack` | Acknowledge |
| POST 🔒 | `/alerts/test` | `{channel: default/slack/teams/both}` send a test message |
| POST | `/alerts/webhook` | **Alertmanager receiver**, `Authorization: Bearer <ALERTMANAGER_WEBHOOK_TOKEN>` |

Rule body:

```json
{
  "name": "Production daily spend above $2,000",
  "metric": "daily_cost",
  "provider": null, "environment": "production", "resource_type": null,
  "operator": ">", "threshold": 2000,
  "severity": "warning", "channels": "default", "enabled": true
}
```

## Sync & cloud accounts

| Method | Path | Description |
|---|---|---|
| GET | `/sync/status` | Data source, per-provider configuration and last run, scheduled jobs |
| GET | `/sync/runs?limit=50` | Sync history |
| POST 🔒 | `/sync/run` | `{job: manual/daily/intraday/metrics/backfill, providers?}` → 202, runs in background |
| POST 🔒 | `/sync/test/{provider}` | Credential and connectivity check |
| POST 🔒 | `/sync/mock/anomaly` | Mock mode only: `{provider, factor, days_ago}` injects a cost spike |
| DELETE 🔒 | `/sync/mock/anomaly` | Clear injected spikes |

## Settings & reports

| Method | Path | Description |
|---|---|---|
| GET | `/settings` | Budgets, exchange rate, channel, thresholds + read-only `system` block |
| PUT 🔒 | `/settings` | Partial update |
| GET | `/reports/summary?start=&end=` | Report for **any range** (e.g. last 6 months): total, daily average, previous period of equal length (`complete` = data exists for all of it), budget pro-rated to the days in the range, **monthly breakdown** (per provider, budget %, change), breakdowns, top services/resources, anomalies, recommendations |
| GET | `/reports/summary.csv?start=&end=` | Same as CSV, file `cloudlens_report_<start>_to_<end>.csv` |
| GET | `/reports/monthly?month=YYYY-MM` | Shortcut: the summary for one calendar month (a future month returns 422) |
| GET | `/reports/monthly.csv?month=YYYY-MM` | Same as CSV |

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{status, database, data_source, version}`; 503 if the DB is down |
| GET | `/metrics` | Prometheus exposition format |

### Prometheus metrics

| Metric | Labels |
|---|---|
| `cloudlens_alert_rule_value`, `_threshold`, `_breached` | rule_id, rule_name, metric, severity, provider, environment |
| `cloudlens_cost_mtd_usd`, `cloudlens_cost_forecast_usd` | provider |
| `cloudlens_cost_last_day_usd` | provider, environment |
| `cloudlens_budget_used_ratio` | scope |
| `cloudlens_resource_cpu_percent`, `cloudlens_resource_memory_percent` | provider, resource, environment, resource_type |
| `cloudlens_sync_last_success_timestamp_seconds`, `cloudlens_sync_last_run_success` | provider |
| `cloudlens_http_requests_total`, `cloudlens_http_request_duration_seconds` | method, route, status |
