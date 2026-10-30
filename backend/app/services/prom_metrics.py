"""Prometheus metrics exposed at GET /metrics and scraped by the Prometheus container.

Alert rules defined in the dashboard are exported as `cloudlens_alert_rule_breached` gauges;
monitoring/prometheus/alert_rules.yml turns them into Prometheus alerts that Alertmanager routes
back to the backend webhook, which notifies Slack / Microsoft Teams.
"""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry(auto_describe=True)
RULE_LABELS = ["rule_id", "rule_name", "metric", "severity", "provider", "environment"]

rule_value = Gauge("cloudlens_alert_rule_value", "Current value of the metric watched by an alert rule", RULE_LABELS, registry=REGISTRY)
rule_threshold = Gauge("cloudlens_alert_rule_threshold", "Configured threshold of an alert rule", RULE_LABELS, registry=REGISTRY)
rule_breached = Gauge("cloudlens_alert_rule_breached", "1 when the alert rule condition is met", RULE_LABELS, registry=REGISTRY)

cost_mtd = Gauge("cloudlens_cost_mtd_usd", "Month-to-date cost in USD", ["provider"], registry=REGISTRY)
cost_forecast = Gauge("cloudlens_cost_forecast_usd", "Month-end forecast in USD", ["provider"], registry=REGISTRY)
cost_last_day = Gauge("cloudlens_cost_last_day_usd", "Cost of the last full day in USD", ["provider", "environment"], registry=REGISTRY)
budget_used = Gauge("cloudlens_budget_used_ratio", "Month-to-date cost / monthly budget", ["scope"], registry=REGISTRY)
resource_cpu = Gauge("cloudlens_resource_cpu_percent", "Latest CPU utilization", ["provider", "resource", "environment", "resource_type"], registry=REGISTRY)
resource_mem = Gauge("cloudlens_resource_memory_percent", "Latest memory utilization", ["provider", "resource", "environment", "resource_type"], registry=REGISTRY)
sync_last_success = Gauge("cloudlens_sync_last_success_timestamp_seconds", "Unix time of last successful sync", ["provider"], registry=REGISTRY)
sync_last_ok = Gauge("cloudlens_sync_last_run_success", "1 if the last sync run succeeded or was skipped", ["provider"], registry=REGISTRY)

http_requests = Counter("cloudlens_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=REGISTRY)
http_latency = Histogram("cloudlens_http_request_duration_seconds", "HTTP request latency", ["method", "route"], registry=REGISTRY,
                         buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
