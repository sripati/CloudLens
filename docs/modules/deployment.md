# Module: Containers & Deployment

**Paths:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`,
`monitoring/mock-receiver/Dockerfile`, `deploy/aws/*`, `scripts/*`, `Makefile`

## Images

| Image | Base | Highlights |
|---|---|---|
| backend | python:3.12-slim | includes the cloud SDKs; non-root uid 10001; healthcheck on `/health`; 1 uvicorn worker |
| frontend | node:20-alpine → nginx:1.27-alpine | Multi-stage; SPA fallback; gzip; 1-year cache for `/assets`; proxies `/api`, `/health`, `/docs`, `/mock-inbox/`; security headers |
| mock-receiver | python:3.12-slim | Non-root; about 60 MB |

nginx resolves upstreams at request time (`resolver 127.0.0.11` + variables), so the frontend starts
even if the backend is still booting.

## Compose details

- `db` healthcheck gates `backend` startup (`depends_on: condition: service_healthy`).
- `x-logging` anchor: json-file logs capped at 10 MB × 3 per container.
- Volumes: `pgdata`, `promdata`, `amdata` (data survives `docker compose down`; `down -v` deletes it).
- Ports: only `HTTP_PORT` is public; the API, Prometheus, Alertmanager and mock receiver bind to `127.0.0.1`.
- Volume `alertshared` is shared by the backend (`/shared`) and Alertmanager (read-only), for the Slack webhook URL.

## Scripts

| Script | Purpose |
|---|---|
| `deploy/aws/create-ec2.sh` | Security group, IAM role, t3.small instance with user data |
| `deploy/aws/ec2-user-data.sh` | Installs Docker + Compose, 2 GB swap |
| `deploy/aws/deploy.sh` | rsync → upload `.env.staging` → `compose up --build` → health wait |
| `deploy/aws/iam-policy.json` | Least-privilege read-only policy |
| `scripts/backup_db.sh` | pg_dump (keeps 14) and restore |
| `scripts/screenshots.py` | Playwright captures of every screen, both themes, plus mobile |
| `Makefile` | `make up / down / logs / test / backup / screenshots` |

Step-by-step guide: [../deployment-ec2.md](../deployment-ec2.md).
