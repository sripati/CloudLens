# Module: Monitoring Stack & Mock Receiver

**Path:** `monitoring/`

## Prometheus (`monitoring/prometheus/`)

- `prometheus.yml`: scrape interval 30 s; jobs `cloudlens-backend` (`backend:8000/metrics`),
  `prometheus`, `alertmanager`; alerting to `alertmanager:9093`; loads `alert_rules.yml`.
- `alert_rules.yml`: `CloudLensRuleBreached` (bridges dashboard rules) and four platform alerts.
  Details in [alerting.md](../alerting.md#3-prometheus-rules-monitoringprometheusalert_rulesyml).
- Retention: `PROMETHEUS_RETENTION` (15d). Lifecycle API is enabled: `curl -X POST localhost:9090/-/reload`.
- Validate: `promtool check rules monitoring/prometheus/alert_rules.yml`.

## Alertmanager (`monitoring/alertmanager/alertmanager.tmpl.yml`)

- Default receiver `cloudlens-backend`: webhook to `/api/v1/alerts/webhook` with a bearer token,
  `send_resolved: true`.
- Route `route="infra"` goes to the `infra-direct` receiver (Slack directly) for backend-down alerts.
- Grouping: `alertname, rule_id, provider`; `group_wait 30s`, `group_interval 5m`, `repeat_interval 4h`.
- Inhibition: BackendDown suppresses Sync* and DataStale alerts.
- `__WEBHOOK_TOKEN__` is replaced at container start (see the compose entrypoint). The Slack URL comes from `/shared/slack_webhook_url`, written by the backend.
- Validate: `amtool check-config <rendered file>`.

## Mock receiver (`monitoring/mock-receiver/app.py`)

A small FastAPI app standing in for Slack and Teams:

| Endpoint | Purpose |
|---|---|
| `POST /slack` | Accepts Block Kit payloads (returns `ok` like Slack) |
| `POST /teams` | Accepts Adaptive Card payloads |
| `GET /messages?channel=` | JSON inbox, newest first (max 500, in memory) |
| `DELETE /messages` | Clear |
| `GET /` | Auto-refreshing HTML inbox (through nginx at `/mock-inbox/`) |

Use it in development, CI and the viva demo. In production, point the webhook URLs at real
Slack and Teams and remove the service and its nginx location.

## Optional: Grafana

All cost and utilization metrics are in Prometheus, so Grafana can be added:

```yaml
  grafana:
    image: grafana/grafana:11.3.0
    ports: ["127.0.0.1:3000:3000"]
```

Add Prometheus (`http://prometheus:9090`) as a data source and chart `cloudlens_cost_mtd_usd` and the other metrics.
