# Module Documentation

One file per module: what it does, its key functions, how it connects to the rest, and how to extend it.

| # | Module | Path | Doc |
|---|---|---|---|
| 1 | Core: config, database, security | `backend/app/core/` | [core.md](core.md) |
| 2 | Data models | `backend/app/models/` | [models.md](models.md) |
| 3 | Cloud provider connectors | `backend/app/services/providers/` | [providers.md](providers.md) |
| 4 | Normalizer | `backend/app/services/normalizer.py` | [normalizer.md](normalizer.md) |
| 5 | Ingestion (aggregation & storage) | `backend/app/services/ingestion.py` | [ingestion.md](ingestion.md) |
| 6 | Analytics | `backend/app/services/analytics.py` | [analytics.md](analytics.md) |
| 7 | Alert engine | `backend/app/services/alert_engine.py`, `prom_metrics.py` | [alert-engine.md](alert-engine.md) |
| 8 | Notifier (Slack / Teams) | `backend/app/services/notifier.py` | [notifier.md](notifier.md) |
| 9 | Scheduler | `backend/app/services/scheduler.py` | [scheduler.md](scheduler.md) |
| 10 | Auth & RBAC | `backend/app/api/deps.py`, `routes/auth.py` | [auth-rbac.md](auth-rbac.md) |
| 11 | REST API routes | `backend/app/api/routes/` | [api-routes.md](api-routes.md) |
| 12 | Settings service | `backend/app/services/settings_service.py` | [settings.md](settings.md) |
| 13 | Frontend application | `frontend/src/` | [frontend.md](frontend.md) |
| 14 | Monitoring stack & mock receiver | `monitoring/` | [monitoring.md](monitoring.md) |
| 15 | Containers & deployment | `docker-compose.yml`, `*/Dockerfile`, `deploy/` | [deployment.md](deployment.md) |

Screen-level docs are in [../screens/](../screens/).

## Request lifecycle (example: Dashboard load)

```
Browser ──GET /api/v1/dashboard/overview?days=30&provider=aws──► nginx (frontend container)
  └─► backend: deps.get_current_user (JWT) → deps.get_filters (validate) → routes/dashboard.overview
        └─► analytics.summary / daily_series / breakdown / utilization / resources / anomalies
              └─► SQLAlchemy → PostgreSQL (GROUP BY on indexed columns)
  ◄── JSON ── React DashboardPage renders KpiCard, CostTrendChart, DonutChart, BarList, ...
```
