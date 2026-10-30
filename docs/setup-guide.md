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
| `DATA_SOURCE` | `mock` | `mock` = generator, `live` = real cloud APIs |
| `ENABLED_PROVIDERS` | `aws,azure,gcp` | Providers to sync |
| `ENV_TAG_KEY` | `environment` | Tag/label holding the environment name |
| `BACKFILL_DAYS` | `180` | History loaded on first start |
| `SYNC_LOOKBACK_DAYS` | `3` | Days re-fetched by the daily sync |
| `METRICS_INTERVAL_MINUTES` | `5` | Utilization sampling interval |
| `INTRADAY_COST_REFRESH_MINUTES` | `15` | Today's cost refresh. **Use 360+ in live mode.** |
| `ALERT_DELIVERY` | `alertmanager` | `alertmanager` (Docker) or `direct` |
| `SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL` | mock receiver | Incoming-webhook URLs |
| `DEFAULT_NOTIFICATION_CHANNEL` | `both` | `slack`, `teams` or `both` |
| `DEFAULT_MONTHLY_BUDGET_USD` | `120000` | Initial budget (editable in Settings) |
| `DEFAULT_EXCHANGE_RATE_INR` | `84.20` | Initial INR rate (editable in Settings) |

## 5. Switching to live cloud data

Set `DATA_SOURCE=live` in `.env`, fill in the credentials for the providers you use, and restart:
`docker compose up -d backend`. Providers without credentials are **skipped** (shown on Cloud Accounts)
while the others keep working. Use **Cloud Accounts → Test connection** to verify each one.

To start the history fresh from live data, clear the mock rows first:
`docker compose exec db psql -U cloudlens -c "TRUNCATE cost_records, resource_metrics, resources, sync_runs;"`.
Then restart the backend; it backfills `BACKFILL_DAYS` on start.

### 5.1 AWS

1. **Enable Cost Explorer** in the Billing console (it takes up to 24 hours the first time).
2. **Activate the cost allocation tag** `environment` (Billing → Cost allocation tags) so costs can be
   grouped by environment. Tag your resources `environment=prod|staging|dev`.
3. Credentials, either:
   - **EC2 instance role (recommended):** attach a role with `deploy/aws/iam-policy.json` and set
     `AWS_USE_DEFAULT_CREDENTIALS=true`, or
   - **IAM user:** create a user with that policy, create access keys, then set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`.
4. Set `AWS_REGIONS` to the regions where your EC2 and RDS resources run (comma separated).

APIs used: `ce:GetCostAndUsage` (DAILY, UnblendedCost, grouped by SERVICE and the environment tag),
`ec2:DescribeInstances`, `rds:DescribeDBInstances`, `cloudwatch:GetMetricData` (CPUUtilization).
**Cost:** each Cost Explorer request costs USD 0.01. A daily sync of 3 days typically makes 1–2 requests.

### 5.2 Azure

1. Create a service principal:
   ```bash
   az ad sp create-for-rbac --name cloudlens-reader --role "Cost Management Reader" \
     --scopes /subscriptions/<SUBSCRIPTION_ID>
   az role assignment create --assignee <appId> --role "Monitoring Reader" --scope /subscriptions/<SUBSCRIPTION_ID>
   az role assignment create --assignee <appId> --role "Reader" --scope /subscriptions/<SUBSCRIPTION_ID>
   ```
2. Copy `appId → AZURE_CLIENT_ID`, `password → AZURE_CLIENT_SECRET`, `tenant → AZURE_TENANT_ID` and set
   `AZURE_SUBSCRIPTION_ID`.
3. Tag resources with `environment`.

APIs used: Cost Management Query API (ActualCost, Daily, grouped by ServiceName, ResourceLocation and the
environment tag; queried in 7-day windows), Resource Manager `resources.list`, and Azure Monitor metrics
(`Percentage CPU`, `node_cpu_usage_percentage`, `cpu_percent`, `CpuPercentage`). Costs billed in INR are
converted to USD with the Settings exchange rate.

### 5.3 GCP

The Cloud Billing API exposes billing accounts and budgets but **not daily cost lines**. Google's
supported source for cost data is the **Cloud Billing export to BigQuery**:

1. Billing → Billing export → **Standard usage cost** → enable export to a BigQuery dataset
   (for example `billing_export`). Data starts flowing within a day.
2. Create a service account with **BigQuery Data Viewer**, **BigQuery Job User**, **Monitoring Viewer**
   and **Billing Account Viewer** (on the billing account), then download a JSON key.
3. Save the key as `secrets/gcp-key.json` and set:
   ```
   GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-key.json
   GCP_PROJECT_ID=<project>
   GCP_BILLING_ACCOUNT_ID=<XXXXXX-XXXXXX-XXXXXX>
   GCP_BILLING_EXPORT_TABLE=<project>.billing_export.gcp_billing_export_v1_<BILLING_ACCOUNT_ID_WITH_UNDERSCORES>
   ```
4. Label resources with `environment`.

APIs used: BigQuery (partition-filtered query with a 2 GB `maximum_bytes_billed` guard),
Cloud Billing `getBillingInfo` for the connection test, and Cloud Monitoring
`compute.googleapis.com/instance/cpu/utilization`.

## 6. Slack and Microsoft Teams

- **Slack:** create an app → *Incoming Webhooks* → add to a channel → copy the URL into `SLACK_WEBHOOK_URL`.
- **Teams:** in the channel, choose *Workflows* → "Post to a channel when a webhook request is received" →
  copy the URL into `TEAMS_WEBHOOK_URL`. The legacy Office 365 connector URL also accepts the same Adaptive Card.
- Restart the backend and Alertmanager: `docker compose up -d backend alertmanager`.
- Test from **Alerts → Test notification**.

## 7. Default accounts

| Email | Password | Role |
|---|---|---|
| `ADMIN_EMAIL` (admin@cloudlens.dev) | `ADMIN_PASSWORD` (Admin@123) | admin |
| `VIEWER_EMAIL` (viewer@cloudlens.dev) | `VIEWER_PASSWORD` (Viewer@123) | viewer |

They are created only when the users table is empty. Change the passwords in `.env` before the first
start, or later in **Settings → Change password**.
