# Module: REST API Routes

**Path:** `backend/app/api/routes/`. Registered in `app/main.py` under `API_PREFIX` (`/api/v1`).
Full endpoint list: [../api-reference.md](../api-reference.md).

| File | Router prefix | Responsibility |
|---|---|---|
| `auth.py` | `/auth`, `/users` | Login, me, change password, user CRUD (admin) |
| `dashboard.py` | `/dashboard` | `summary`, `overview` (single call for the Dashboard screen) |
| `costs.py` | `/costs` | daily, breakdown, monthly, anomalies, filters, CSV export |
| `resources.py` | `/resources` | list, utilization, recommendations, detail |
| `alerts.py` | `/alerts` | metric catalog, rule CRUD, evaluate, events, ack, test, **Alertmanager webhook** |
| `sync.py` | `/sync` | status, runs, trigger, test connection, mock anomaly inject/clear |
| `settings.py` | `/settings` | read (all) / update (admin) |
| `reports.py` | `/reports` | monthly JSON and CSV |

## main.py

- `lifespan`: `init_db()` → `seed()` → `scheduler.start()`; on shutdown `scheduler.shutdown()`.
- CORS from `CORS_ORIGINS`.
- HTTP middleware records `cloudlens_http_requests_total` and the latency histogram per route template.
- `/health` checks the database (503 when down, used by Docker healthchecks and `deploy.sh`).
- `/metrics` serves the custom Prometheus registry.

## Conventions

- Routes are thin: validate input (Pydantic + `get_filters`), call a service function, return a dict or model.
- Write routes depend on `require_admin`; read routes on `get_current_user`.
- Long work (syncs) runs in a background thread and returns **202**.
- Errors use `HTTPException` with human-readable `detail` (shown directly in the UI).

## Adding an endpoint

1. Put the logic in a service (`app/services/...`), not in the route.
2. Add the route with the right dependency, and include its router in `main.py` if it is a new file.
3. Add an API test in `tests/test_api.py` (including a viewer 403 check for write routes).
