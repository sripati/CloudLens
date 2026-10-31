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
| `environment` | `production` | production, staging, development, unassigned (the screens offer only the first three) |
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
| GET | `/sync/status` | Overall `data_source` (`mock`, `live` or `mixed`), each provider's `mode`, `connections` (environment, account, verified, last run) and last run, scheduled jobs |
| GET | `/sync/runs?limit=50` | Sync history |
| POST 🔒 | `/sync/run` | `{job: manual/daily/intraday/metrics/backfill, providers?}` → 202, runs in background |
| POST 🔒 | `/sync/test/{provider}` | Re-tests every saved connection of the cloud |
| POST 🔒 | `/sync/mock/anomaly` | Clouds in Mock mode only: `{provider, factor, days_ago}` injects a cost spike |
| DELETE 🔒 | `/sync/mock/anomaly` | Clear injected spikes |

## Cloud accounts

All admin only. `provider` is `aws`, `azure` or `gcp`. `environment` is `production`, `staging` or `development`. Secret values are never returned.

| Method | Path | Description |
|---|---|---|
| GET 🔒 | `/cloud-accounts/{provider}?environment=` | Mode, saved connections, form fields, non-secret values, which secrets are set, validation state, prerequisites, cost note |
| POST 🔒 | `/cloud-accounts/{provider}/test` | `{environment, config}`: checks formats (422 per field), then calls the cloud. Returns `{ok, message, account, checks[], api_calls}`. Fails if another environment uses the account. Saves nothing. A blank secret means "use the saved one" |
| PUT 🔒 | `/cloud-accounts/{provider}/config` | `{environment, config, activate}`: saves values that passed a test; 409 otherwise, or if the account is in use. `activate: true` also switches to Live |
| PUT 🔒 | `/cloud-accounts/{provider}/mode` | `{mode: mock or live}`. `live` needs at least one validated connection, otherwise 409. Starts a background data load |
| DELETE 🔒 | `/cloud-accounts/{provider}/config?environment=` | Forgets that connection, and its figures stop showing. Removing the last one returns the cloud to Mock. Collected data is kept |

## Settings & reports

| Method | Path | Description |
|---|---|---|
| GET | `/settings` | Budgets, exchange rate, channel, thresholds + read-only `system` block |
| PUT 🔒 | `/settings` | Partial update. `slack_webhook_url` and `teams_webhook_url` must start with `https://`; omit to keep, `""` returns to the test inbox. Never returned; `system.webhooks` reports only whether each is saved |
| GET | `/reports/summary?start=&end=&provider=&environment=&resource_type=` | Report for **any range**, narrowed by the filters; the budget is the selected cloud's own (`budget_scope`), and `budget_applies_to_filtered_view` is false when environment or type narrows the cost further (e.g. last 6 months): total, daily average, previous period of equal length (`complete` = data exists for all of it), budget pro-rated to the days in the range, **monthly breakdown** (per provider, budget %, change), breakdowns, top services/resources, anomalies, recommendations |
| GET | `/reports/summary.csv?start=&end=&provider=&environment=&resource_type=` | Same as CSV, with a *Filters* row, file `cloudlens_report_<start>_to_<end>.csv` |
| GET | `/reports/monthly?month=YYYY-MM` | Shortcut: the summary for one calendar month (a future month returns 422) |
| GET | `/reports/monthly.csv?month=YYYY-MM` | Same as CSV |

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{status, database, data_source, version}` (`data_source`: `mock`, `live` or `mixed`); 503 if the DB is down |
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
