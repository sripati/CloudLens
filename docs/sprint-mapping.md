# Sprint Plan → Delivery Mapping

The project was delivered in one pass rather than sprint by sprint. This table shows where every task
and goal from the six sprints is implemented, so it can be checked during evaluation.

## Sprint 1: Project setup and basic cloud integration

| Task | Delivered in |
|---|---|
| Repository, folder structure, initial requirements | Repo layout (README §Project structure), `backend/requirements*.txt`, `frontend/package.json`, `Makefile` |
| Connect to AWS, Azure, GCP APIs; verify access | `backend/app/services/providers/aws.py`, `azure.py`, `gcp.py`; **Cloud Accounts → Test connection** (`POST /sync/test/{provider}`) |
| Environment variables and credentials | `.env.example` (all providers), `app/core/config.py`, `secrets/`, IAM policy `deploy/aws/iam-policy.json` |
| Pull sample data, analyse format | Parsers `parse_cost_explorer`, `parse_cost_query`, `parse_billing_rows` with unit tests on real response shapes; field mapping in [database.md](database.md#unified-cost-schema-the-heart-of-the-system) |
| **Goal:** connectivity + initial data | Mock/live switch (`DATA_SOURCE`), sync history with API-call counts |

## Sprint 2: Data aggregation and storage

| Task | Delivered in |
|---|---|
| Aggregation scripts, unified format | `services/providers/base.py` (`CostItem`, `ResourceItem`, `MetricItem`), `services/normalizer.py` |
| Data schema + PostgreSQL | `app/models/*`, [database.md](database.md) (ER diagram, constraints, indexes) |
| Scheduled daily jobs | `services/scheduler.py` (daily 02:00, intraday 15 min, metrics 5 min, retention 03:30) |
| Test storage and retrieval consistency | `tests/test_ingestion_analytics.py`: idempotent re-sync, duplicate merge, breakdowns sum to total, daily series = total |
| **Goal:** standardized collection | Idempotent upserts on natural keys; `sync_runs` audit |

## Sprint 3: Real-time dashboard

| Task | Delivered in |
|---|---|
| Frontend dashboard (React.js) | `frontend/src/pages/DashboardPage.jsx` (approved design), dark/light theme, USD/INR |
| APIs from DB → dashboard | `/dashboard/overview`, `/dashboard/summary`, `/costs/*`, `/resources/*` |
| Basic filters (provider, type, environment) | `components/FilterBar.jsx`, shared across screens; server-side `get_filters` |
| Test functionality and accuracy | `tests/test_api.py`, Playwright screenshots in `docs/screenshots/` |
| **Goal:** real-time view | 5-min utilization sampling, 15-min today's cost, 60 s auto-refresh |

## Sprint 4: Historical analysis and visualization

| Task | Delivered in |
|---|---|
| Backend trend logic (monthly change, utilization rates) | `analytics.monthly` (MoM, run-rate), `daily_series` (7-day MA), `utilization` (healthy rate, hourly trend), `anomalies` |
| Line charts, bar graphs | `CostTrendChart`, `MonthlyBarChart`, `UtilizationChart`, `DonutChart`, `BarList` |
| Advanced filters (date range, type, provider) | `DateRangePicker`: calendar with presets computed from today and validated custom ranges; Cost Explorer group-by, breakdown by 6 dimensions, monthly view of the selected range; Reports for any range |
| Validate calculations | Analytics tests; Reports screen cross-checks |
| **Goal:** trends over time | Cost Explorer + Reports (monthly, CSV export) |

## Sprint 5: Alerting and notifications

| Task | Delivered in |
|---|---|
| Prometheus Alertmanager monitoring thresholds | `monitoring/prometheus/*`, `monitoring/alertmanager/alertmanager.tmpl.yml`, backend `/metrics` |
| Slack / Teams integration | `services/notifier.py` (Block Kit + Adaptive Card), preference in Settings, per-rule override |
| User-defined alert criteria in the dashboard | Alerts screen (create/edit/disable/delete rules, 8 metrics, scope, severity, channel) |
| Document and test alerting | [alerting.md](alerting.md); `tests/test_alerts.py`; end-to-end run with real Prometheus + Alertmanager; mock receiver |
| **Goal:** proactive notifications | Budget, forecast, anomaly, CPU, idle rules seeded |

## Sprint 6: Testing, documentation, deployment

| Task | Delivered in |
|---|---|
| Extensive testing | 84 backend tests (SQLite + PostgreSQL), 31 frontend tests, E2E alert pipeline, UI screenshots; [testing.md](testing.md) |
| User documentation (setup, usage, troubleshooting) | [setup-guide.md](setup-guide.md), [user-guide.md](user-guide.md), [troubleshooting.md](troubleshooting.md), `docs/modules/*`, `docs/screens/*` |
| Containerize with Docker | `backend/Dockerfile`, `frontend/Dockerfile`, `monitoring/mock-receiver/Dockerfile`, `docker-compose.yml` |
| Deploy to staging | `deploy/aws/create-ec2.sh`, `ec2-user-data.sh`, `deploy.sh`; [deployment-ec2.md](deployment-ec2.md) |
| **Goal:** production-ready | RBAC, health checks, log rotation, backups, hardening checklist |

## Evaluation criteria coverage

| Criterion | Weight | Where to look |
|---|---|---|
| Documentation | 15 % | `docs/` (guides, 12 module docs, 10 screen docs), project report (Word + PDF), viva slides |
| Implementation | 75 % | `backend/`, `frontend/`, `monitoring/`, `deploy/`, tests |
| Cost optimization | 10 % | [cost-optimization.md](cost-optimization.md), recommendations engine, savings KPI, API-call minimization |
