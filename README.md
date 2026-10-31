# CloudLens: DevOps Dashboard for Resource and Cost Monitoring

CloudLens is a centralized dashboard that aggregates **cost** and **resource utilization** data from
**AWS, Azure and GCP**. It shows real-time and historical trends, supports filters and drill-down by provider,
environment and resource type, and sends **alerts to Slack and Microsoft Teams** through
**Prometheus Alertmanager** when costs cross thresholds or resources are over- or under-utilized.

> Capstone project: *DevOps Dashboard for Resource and Cost Monitoring*

| | |
|---|---|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2, APScheduler |
| **Database** | PostgreSQL 16 (historical data and trend analysis) |
| **Frontend** | React 18 (JavaScript) + Vite + Recharts, dark and light themes |
| **Cloud APIs** | AWS Cost Explorer / EC2 / RDS / CloudWatch, Azure Cost Management / Monitor, GCP Cloud Billing + BigQuery billing export / Cloud Monitoring |
| **Alerting** | Prometheus + Alertmanager → backend webhook → Slack / Microsoft Teams |
| **Auth** | JWT, role-based access (Admin, Viewer) |
| **Deployment** | Docker Compose (6 containers), AWS EC2 staging |

---

## Features

- **Unified multi-cloud view.** Costs from all three providers are normalized into one schema covering
  provider, account, day, service, resource type, environment, region and resource.
- **Mock / live switch.** `DATA_SOURCE=mock` runs everything with a realistic deterministic data generator.
  `DATA_SOURCE=live` calls the real cloud APIs with the credentials in `.env`.
- **Real-time view.** Utilization is sampled every 5 minutes, today's running cost every 15 minutes, and the
  dashboard auto-refreshes every 60 seconds.
- **Historical analysis.** Daily trends with a 7-day moving average, month-over-month changes,
  breakdowns by any dimension, anomaly detection, and 365 days of history loaded on first start.
- **Filters and drill-down.** Filter by provider, environment, resource type and date range. The date-range calendar offers
  presets computed from today (last 7/30/90 days, this/last month, last 3/6/12 months, year to date) or any custom range,
  with validation: no future dates, start on or before end, at most 731 days.
  Click any resource for its own cost and utilization history.
- **Customizable alerting.** Eight metric types: daily cost, MTD cost, budget %, forecast %,
  anomaly %, CPU, memory and idle-resource count. Each rule can be scoped by provider, environment or type,
  with a severity and a choice of Slack, Teams or both.
- **Cost optimization.** Rule-based recommendations (stop idle, rightsize, off-hours schedule, storage
  tiering) with estimated monthly savings.
- **Currency.** Display amounts in USD or INR, with a configurable exchange rate.
- **RBAC.** Admins manage rules, accounts, users and settings. Viewers have read-only access.

## Quick start (Docker)

```bash
cp .env.example .env              # set POSTGRES_PASSWORD, JWT_SECRET, admin password
docker compose up -d --build
```

| URL | What |
|---|---|
| http://localhost:8080 | Dashboard (login `admin@cloudlens.dev` / `Admin@123` unless changed in `.env`) |
| http://localhost:8080/docs | Swagger API documentation |
| http://localhost:8080/mock-inbox/ | Mock Slack/Teams inbox (alerts land here by default) |
| http://localhost:9090 | Prometheus (localhost only) |
| http://localhost:9093 | Alertmanager (localhost only) |

The first start loads 365 days of history (a few seconds in mock mode). If you raise `BACKFILL_DAYS` later, the
missing older days are fetched on the next restart.

## Local development (without Docker)

```bash
# backend (needs PostgreSQL running locally)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://cloudlens:cloudlens@localhost:5432/cloudlens ALERT_DELIVERY=direct
uvicorn app.main:app --reload            # http://localhost:8000/docs

# frontend
cd frontend && npm install && npm run dev   # http://localhost:5173 (proxies /api to :8000)

# mock Slack/Teams receiver (optional)
cd monitoring/mock-receiver && uvicorn app:app --port 9000
```

## Tests

```bash
make test            # backend (pytest, 84 tests) + frontend (vitest, 31 tests)
make test-backend-pg # same backend suite against PostgreSQL
```

## Project structure

```
.
├── backend/                 FastAPI service (API, scheduler, providers, alert engine)
│   ├── app/core/            config, database, security
│   ├── app/models/          SQLAlchemy tables
│   ├── app/schemas/         Pydantic request/response models
│   ├── app/api/routes/      REST endpoints
│   ├── app/services/        ingestion, analytics, alert engine, notifier, scheduler
│   │   └── providers/       aws.py, azure.py, gcp.py, mock.py
│   └── tests/               pytest suite
├── frontend/                React dashboard (Vite)
│   └── src/{pages,components,context,hooks,api,utils,styles}
├── monitoring/
│   ├── prometheus/          scrape config + alert rules
│   ├── alertmanager/        routing template
│   └── mock-receiver/       fake Slack/Teams webhook endpoint
├── deploy/aws/              EC2 creation, bootstrap, deploy scripts, IAM policy
├── scripts/                 screenshots, database backup
├── docs/                    full documentation (modules, screens, guides, report)
├── docker-compose.yml
└── .env.example
```

## Documentation

| Document | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, technology choices |
| [docs/setup-guide.md](docs/setup-guide.md) | Installation, configuration and live cloud credentials |
| [docs/user-guide.md](docs/user-guide.md) | How to use every screen |
| [docs/api-reference.md](docs/api-reference.md) | REST endpoints |
| [docs/database.md](docs/database.md) | Schema, indexes, retention |
| [docs/alerting.md](docs/alerting.md) | Prometheus → Alertmanager → Slack/Teams pipeline |
| [docs/deployment-ec2.md](docs/deployment-ec2.md) | Staging deployment on AWS EC2 |
| [docs/testing.md](docs/testing.md) | Test strategy and results |
| [docs/cost-optimization.md](docs/cost-optimization.md) | Savings features and the platform's own running cost |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common problems and fixes |
| [docs/sprint-mapping.md](docs/sprint-mapping.md) | How each sprint task and goal is delivered |
| [docs/future-enhancements.md](docs/future-enhancements.md) | Roadmap |
| [docs/modules/](docs/modules/) | One file per backend/frontend module |
| [docs/screens/](docs/screens/) | One file per UI screen |
| [docs/report/](docs/report/) | Project report (Word + PDF) |
