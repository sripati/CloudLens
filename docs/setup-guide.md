# Setup Guide

## 1. Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Docker Desktop / Docker Engine | 24+ with Compose v2 | Running the full stack |
| Python | 3.12 (3.11+ works) | Backend development and tests |
| Node.js | 20 LTS | Frontend development |
| PostgreSQL | 16 | Only when running the backend outside Docker |

## 2. Run with Docker (recommended)

```bash
git clone <repo> cloudlens && cd cloudlens
cp .env.example .env
```

Edit `.env` and change at least these values:

```
POSTGRES_PASSWORD=<strong password>
JWT_SECRET=<random string, 32+ characters>     # e.g. openssl rand -hex 32
ADMIN_PASSWORD=<your admin password>
ALERTMANAGER_WEBHOOK_TOKEN=<random string>
```

Then start the stack:

```bash
docker compose up -d --build
docker compose ps               # all services "running"/"healthy"
docker compose logs -f backend  # watch the initial backfill
```

Open http://localhost:8080 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## 3. Run for development (hot reload)

```bash
# PostgreSQL in Docker only
docker compose up -d db

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://cloudlens:<POSTGRES_PASSWORD>@localhost:5432/cloudlens
export ALERT_DELIVERY=direct SLACK_WEBHOOK_URL=http://localhost:9000/slack TEAMS_WEBHOOK_URL=http://localhost:9000/teams
uvicorn app.main:app --reload --port 8000

# Mock Slack/Teams receiver (another terminal)
cd monitoring/mock-receiver && pip install fastapi uvicorn && uvicorn app:app --port 9000

# Frontend (another terminal)
cd frontend && npm install && npm run dev     # http://localhost:5173
```

> To reach the `db` container from your machine, add a `ports: ["127.0.0.1:5432:5432"]` mapping
> under `db` in `docker-compose.yml`, or use a local PostgreSQL install.

## 4. Configuration reference

All settings are environment variables; `.env.example` documents every one. The most important:

| Variable | Default | Meaning |
|---|---|---|
| `ENABLED_PROVIDERS` | `aws,azure,gcp` | Providers to sync |
| `BACKFILL_DAYS` | `365` | History loaded on first start; raising it later fetches the missing older days on the next restart |
| `SYNC_LOOKBACK_DAYS` | `3` | Days re-fetched by the daily sync |
| `METRICS_INTERVAL_MINUTES` | `5` | Utilization sampling interval |
| `INTRADAY_COST_REFRESH_MINUTES` | `15` | How often the job that refreshes today's cost runs |
| `ALERT_DELIVERY` | `alertmanager` | `alertmanager` (Docker) or `direct` |
| `DEFAULT_NOTIFICATION_CHANNEL` | `both` | `slack`, `teams` or `both` |
| `DEFAULT_MONTHLY_BUDGET_USD` | `120000` | Initial budget (editable in Settings) |
| `DEFAULT_EXCHANGE_RATE_INR` | `84.20` | Initial INR rate (editable in Settings) |

## 5. Switching to live cloud data

Every cloud starts in Mock mode. Live connections are set up on the **Cloud Accounts** screen and stored in the database, not in
`.env`. See [live-cloud-setup.md](live-cloud-setup.md).

## 6. Slack and Microsoft Teams

- **Slack:** create an app → *Incoming Webhooks* → add to a channel → copy the URL.
- **Teams:** in the channel, choose *Workflows* → "Post to a channel when a webhook request is received" → copy the URL.
  The legacy Office 365 connector URL also accepts the same Adaptive Card.
- Paste them in **Settings → Notifications** and click **Save settings**. No restart is needed. Until then, alerts go to the test
  inbox at `/mock-inbox/`.
- Test from **Alerts → Test notification**.

## 7. Default accounts

| Email | Password | Role |
|---|---|---|
| `ADMIN_EMAIL` (admin@cloudlens.dev) | `ADMIN_PASSWORD` (Admin@123) | admin |
| `VIEWER_EMAIL` (viewer@cloudlens.dev) | `VIEWER_PASSWORD` (Viewer@123) | viewer |

They are created only when the users table is empty. Change the passwords in `.env` before the first
start, or later in **Settings → Change password**.
