# API Reference

Base path: `/api/v1`. Interactive docs: **`/docs`** (Swagger UI) and **`/redoc`**.
All endpoints except `/auth/login`, `/alerts/webhook`, `/health` and `/metrics` require
`Authorization: Bearer <JWT>`. 🔒 = admin role required.

## Common filter parameters

Accepted by dashboard, costs, resources and recommendations endpoints:

| Param | Example | Notes |
|---|---|---|
| `days` | `30` | Range ending today (default 30), ignored when `start` is given |
| `start`, `end` | `2026-09-01`, `2026-09-30` | Inclusive, max 2 years |
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
| GET | `/costs/monthly?months=6` | Monthly totals per provider with month-over-month change; current month flagged `partial` with `run_rate_change_pct` |
| GET | `/costs/anomalies?threshold_pct=40` | Days where a provider exceeded its trailing 7-day average |
| GET | `/costs/filters` | Distinct providers, environments, types, services, regions, accounts |
| GET | `/costs/export` | CSV of normalized cost lines |

## Resources

| Method | Path | Description |
|---|---|---|
| GET | `/resources?search=&status=&sort=cost` | Inventory with cost, latest and 7-day CPU and memory, status (`healthy`, `idle`, `over_utilized`, `no_metrics`) |
| GET | `/resources/{id}?days=30` | Drill-down: details, tags, daily cost, 7-day metrics, recommendations |
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
| GET | `/reports/monthly?month=YYYY-MM` | Monthly report (totals, breakdowns, top services/resources, anomalies, recommendations) |
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
