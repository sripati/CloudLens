# Module: Alert Engine & Prometheus Export

**Paths:** `backend/app/services/alert_engine.py`, `backend/app/services/prom_metrics.py`

## evaluate_all(db)

Runs every `ALERT_EVAL_INTERVAL_SECONDS` (60) and on rule create/update:

1. Clears the rule gauges (removes deleted or disabled rules from Prometheus).
2. For each enabled rule, `compute_value(db, rule)` returns `(value, detail)`.
3. Compares with `OPS[operator](value, threshold)` → `breached`.
4. Saves `state` (ok/firing), `last_value`, `last_detail` and `last_evaluated_at`.
5. Sets the gauges `cloudlens_alert_rule_value`, `_threshold` and `_breached` with labels
   `rule_id, rule_name, metric, severity, provider, environment`.
6. If `ALERT_DELIVERY=direct` and the state changed, calls `record_event` (which notifies).

One failing rule is logged and skipped; the others still run.

## compute_value

Scope comes from `_scope(rule)`: yesterday as the "last full day", plus the rule's provider, environment
and type. See the metric table in [alerting.md](../alerting.md#2-rule-metrics).
`_resource_extreme` uses only samples newer than max(30 min, 3 × metrics interval), so stale
resources never trigger CPU alerts.

## Webhook handling: handle_alertmanager(db, payload)

- Parses Alertmanager v4 payloads; treats `0001-01-01` as "no end".
- **Deduplication** on (`fingerprint`, `status`, `startsAt`), because Alertmanager repeats notifications every `repeat_interval`.
- Labels with `rule_id` link to the rule (title and message built from the rule). Platform alerts
  (BackendDown, SyncFailing...) use the annotations.
- Each new event → `record_event` → notifier → `alert_events` row with delivery status.

## refresh_metrics(db)

Exports cost and utilization gauges for Grafana or ad-hoc PromQL:
`cloudlens_cost_mtd_usd`, `cloudlens_cost_forecast_usd`, `cloudlens_cost_last_day_usd{provider,environment}`,
`cloudlens_budget_used_ratio{scope}`, `cloudlens_resource_cpu_percent`, `cloudlens_resource_memory_percent`,
`cloudlens_sync_last_success_timestamp_seconds`, `cloudlens_sync_last_run_success`.

## Adding a metric type

1. Add the key and description to `ALERT_METRICS` in `models/alert.py` and its unit to `UNITS`.
2. Implement the branch in `compute_value`.
3. Add a test in `tests/test_alerts.py::test_operators_and_metrics`.
The frontend reads `/alerts/metrics`, so the new metric appears in the rule form automatically.
