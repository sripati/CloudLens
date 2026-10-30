# Alerting and Notifications

## 1. Overview

```
Alerts screen (rules in PostgreSQL)
        │  every 60 s
        ▼
Alert engine (backend) ── computes value per rule ──► /metrics
        │                                             cloudlens_alert_rule_breached{rule_id,rule_name,severity,...}
        ▼
Prometheus  (scrape 30 s, rule CloudLensRuleBreached, for: 1m)
        ▼
Alertmanager (group by alertname+rule_id+provider, group_wait 30 s, repeat 4 h, send_resolved)
        ▼
POST /api/v1/alerts/webhook  (Bearer ALERTMANAGER_WEBHOOK_TOKEN)
        ▼
alert_events row + Notifier ──► Slack (Block Kit)  and/or  Microsoft Teams (Adaptive Card)
```

Rules are defined by users in the dashboard, while Prometheus and Alertmanager provide the standard alert
lifecycle (pending → firing → resolved, grouping, de-duplication, repeat interval, inhibition).

## 2. Rule metrics

| Metric key | Value computed | Typical rule |
|---|---|---|
| `daily_cost` | Cost of the last full day (USD) in scope | AWS daily spend > $1,800 |
| `mtd_cost` | Month-to-date cost (USD) | Dev MTD > $5,000 |
| `budget_used_pct` | MTD ÷ monthly budget × 100 | ≥ 80 % (warning) |
| `forecast_budget_pct` | Forecast ÷ budget × 100 (forecast = full days + 7-day avg × remaining days) | > 100 % (critical) |
| `cost_anomaly_pct` | (last full day − trailing 7-day avg) ÷ avg × 100 | > 40 % (critical) |
| `resource_cpu` | Highest latest CPU % (last 30 min) among resources in scope; detail lists offenders | Production CPU > 80 % |
| `resource_memory` | Same for memory | > 90 % |
| `idle_resource_count` | Resources with 7-day average CPU below the idle threshold (Settings, default 10 %) | > 0 (info) |

Each rule has: scope (provider, environment, resource type), operator (`> >= < <=`), threshold,
severity (`critical | warning | info`), channel (`default | slack | teams | both`), and an enabled flag.
`default` uses **Settings → Notifications → Preferred channel**.

Six rules are seeded on first start (budget 80 %, forecast > budget, anomaly +40 %, production CPU
> 80 %, idle resources, AWS daily > $1,800).

## 3. Prometheus rules (`monitoring/prometheus/alert_rules.yml`)

| Alert | Expression | Severity |
|---|---|---|
| CloudLensRuleBreached | `cloudlens_alert_rule_breached == 1` for 1m | from the rule |
| CloudLensBackendDown | `up{job="cloudlens-backend"} == 0` for 2m | critical (routed directly to Slack) |
| CloudLensSyncFailing | `cloudlens_sync_last_run_success == 0` for 10m | warning |
| CloudLensDataStale | no successful sync for 48 h | warning |
| CloudLensHighApiLatency | p95 latency > 2 s for 10m | info |

If the backend is down it cannot relay notifications, so `CloudLensBackendDown` is labelled `route=infra`
and Alertmanager sends it **straight to Slack** (`infra-direct` receiver). An inhibit rule suppresses
sync and stale alerts while the backend is down.

## 4. Alertmanager config

`monitoring/alertmanager/alertmanager.tmpl.yml` is a template. At container start, `sed` replaces
`__WEBHOOK_TOKEN__` and `__SLACK_WEBHOOK_URL__` with values from `.env`, so no secret is committed.
Clustering is disabled (`--cluster.listen-address=`) because it is a single instance.

## 5. Message formats

**Slack (incoming webhook)**: `text` fallback plus Block Kit header, message, fields (severity, provider,
environment, value, threshold) and a link to the dashboard.

**Teams (Workflows webhook)**: `{"type":"message","attachments":[{"contentType":"application/vnd.microsoft.card.adaptive", ...}]}`
with a coloured title, a FactSet and an *Open CloudLens* button.

Resolved alerts are sent with a `RESOLVED:` prefix.

## 6. Delivery modes

| `ALERT_DELIVERY` | When | Behaviour |
|---|---|---|
| `alertmanager` (default in Docker) | Full stack | Engine only exports gauges; Alertmanager calls the webhook |
| `direct` | Running without Prometheus | Engine notifies on every ok↔firing transition itself |

## 7. Testing alerts

1. **Test message:** Alerts → *Test notification* → choose a channel → Send.
2. **Mock inbox:** open http://localhost:8080/mock-inbox/ (auto-refreshes every 5 s).
3. **Simulate a cost spike (mock mode):** Cloud Accounts → *Demo: simulate a cost spike*. Choose AWS,
   ×2.5, 1 day ago, then *Inject spike*. Within about 2 minutes the *Daily cost anomaly* and *AWS daily spend*
   rules fire, Prometheus shows them at http://localhost:9090/alerts, and Slack and Teams messages arrive. *Clear spikes*
   produces RESOLVED messages.
4. **Create your own rule:** Alerts → New rule (for example `daily_cost > 100` for GCP) → it is evaluated immediately.

Verified end to end during development (Prometheus 2.55.1 + Alertmanager 0.27.0): 4 rules firing → 8 messages
(Slack + Teams each), then RESOLVED messages after the spike was cleared.

## 8. Silencing

Use Alertmanager's UI (http://localhost:9093 → *New Silence*), for example to mute
`alertname="CloudLensRuleBreached", rule_id="5"` during a planned migration. Disabling a rule in the
dashboard also stops it (its gauge goes to 0).
