# Testing

## 1. Strategy

| Level | Tooling | What is covered |
|---|---|---|
| Unit | pytest | Normalizer rules, provider response parsers (AWS, Azure, GCP), mock generator determinism, notifier payloads, channel resolution |
| Integration | pytest + SQLAlchemy (SQLite and **PostgreSQL**) | Backfill, idempotent re-sync, upsert merging, analytics totals and consistency, anomaly detection, recommendations, alert evaluation, Alertmanager webhook |
| API | FastAPI TestClient | Auth, RBAC (viewer 403 on every write), filter validation (422), all endpoints, CSV export |
| Connector | botocore `Stubber` | AWS Cost Explorer pagination through the real boto3 client |
| Frontend unit | Vitest + Testing Library | Currency formatting (USD, INR K/L/Cr), percentages, UI primitives |
| End to end | Real Prometheus 2.55.1 + Alertmanager 0.27.0 + backend + mock receiver | Rule breach → Prometheus alert → Alertmanager → webhook → Slack + Teams; resolve path |
| UI | Playwright (`scripts/screenshots.py`) | Every screen in dark and light themes + phone width; console-error capture |
| Config | `promtool`, `amtool`, `docker compose config` | Prometheus rules and config, Alertmanager config, compose file |

## 2. How to run

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q                                   # SQLite in memory (fast)
TEST_DATABASE_URL=postgresql+psycopg://cloudlens:cloudlens@localhost:5432/cloudlens_test pytest -q
pytest --cov=app --cov-report=term          # coverage

cd ../frontend && npm test                  # vitest
```

The test configuration (`tests/conftest.py`) forces `DATA_SOURCE=mock`, disables the scheduler, removes any
real cloud credentials from the environment, and replaces the notifier with a recorder.

## 3. Results

| Suite | Tests | Result |
|---|---|---|
| Backend on SQLite | 77 | **77 passed** |
| Backend on PostgreSQL 16 | 77 | **77 passed** |
| Backend with pinned `requirements*.txt` in a clean virtualenv | 77 | **77 passed** |
| Frontend (vitest) | 9 | **9 passed** |
| Frontend production build | — | success (no warnings) |
| promtool check rules / config | 5 rules | SUCCESS |
| amtool check-config | — | SUCCESS |
| docker compose config | — | valid |

Backend line coverage: **85 %** overall (analytics 96 %, alert engine 94 %, ingestion 83 %).
The live connectors are about 47 % covered. Their parsing logic is fully tested, while the remaining lines are
SDK calls that need real cloud accounts and are verified with **Cloud Accounts → Test connection**.

### Backend test inventory

| File | Tests | Highlights |
|---|---|---|
| `test_normalizer.py` | 30 | 16 service names across 3 clouds → type; 12 environment spellings; region; INR/GCP conversion |
| `test_providers.py` | 10 | Mock determinism, partial today, anomaly cycles, overrides, metric bounds; AWS/Azure/GCP parsers; unconfigured live providers; AWS Stubber pagination |
| `test_ingestion_analytics.py` | 13 | Backfill of 3 providers / 25 resources; re-sync idempotent; duplicate merge; skipped provider; **breakdowns sum to the total** for 4 dimensions; daily series = total; filters narrow; budget scope; MoM; injected anomaly detected; statuses and recommendations; utilization; drill-down |
| `test_alerts.py` | 9 | Seeded rules; fire → resolve notifications; all 8 metric types compute; provider scope; Prometheus exposition; webhook dedupe and resolve; generic alerts; channels; payload formats |
| `test_api.py` | 15 | Health/metrics; 401s; me; overview shape; 422 validation; costs, resources, reports endpoints; **RBAC 403 for viewer**; rule CRUD with live evaluation; test notification + ack; webhook token; settings round trip; user management guards; sync status and mock anomaly |

## 4. End-to-end alert test (manual / demo)

| Step | Action | Expected | Observed |
|---|---|---|---|
| 1 | Start the backend with `ALERT_DELIVERY=alertmanager`, Prometheus, Alertmanager and the mock receiver | All Prometheus targets UP | ✓ |
| 2 | Cloud Accounts → inject an AWS spike ×2.5 for yesterday | *Daily cost anomaly* and *AWS daily spend* rules → Firing | ✓ |
| 3 | Wait about 1.5 min (`for: 1m` + group_wait 30 s) | Prometheus shows 4 firing alerts; mock inbox receives Slack + Teams messages | ✓ 8 messages |
| 4 | Clear spikes | Rules → OK; RESOLVED messages delivered | ✓ 4 resolved messages |
| 5 | Repeat delivery | Duplicate Alertmanager notifications ignored (same fingerprint + startsAt) | ✓ (unit-tested) |

## 5. Functional test cases (UI)

| ID | Scenario | Steps | Expected |
|---|---|---|---|
| UI-01 | Login failure | Wrong password | Inline error, stays on login |
| UI-02 | Role restriction | Sign in as viewer | No Cloud Accounts / Users in menu; no Sync now / New rule; Settings read-only; direct URL `/users` redirects |
| UI-03 | Theme toggle | Click *Light mode* | All screens switch theme; choice persists after reload |
| UI-04 | Currency | Click *INR ₹* | Amounts in ₹ with K/L/Cr; footer shows the rate |
| UI-05 | Provider filter | Select AWS | KPIs, trend (AWS line only), donut, tables limited to AWS; budget switches to the AWS budget |
| UI-06 | Environment filter | Select Production | Totals drop; budget note says it applies to provider scope |
| UI-07 | Custom range | Cost Explorer → Custom, pick dates | Charts and KPIs cover exactly that range |
| UI-08 | Drill-down | Click a resource row | Resource detail with cost bars, utilization lines, tags, recommendation |
| UI-09 | Create rule | Alerts → New rule (GCP daily cost > 100) | Rule appears and is evaluated immediately (Firing) |
| UI-10 | Test notification | Alerts → Send (Slack) | Event row with delivery *sent*; message in the mock inbox |
| UI-11 | Export | Cost Explorer → Export CSV | CSV downloads with normalized columns |
| UI-12 | Budget change | Settings → budget 200000 → Save | Budget KPI and budget rule update |
| UI-13 | Auto refresh | Leave the dashboard open > 60 s | Footer "Last refreshed" updates; no flicker |
| UI-14 | Responsive | Phone width (390 px) | Sidebar stacks, cards wrap, tables scroll horizontally |

## 6. Data accuracy checks

- Sum of the provider, environment, resource-type and service breakdowns equals the period total (automated).
- Daily series total equals the SQL total for the range (automated).
- Re-running a sync for the same days leaves the row count unchanged (automated).
- Reports month total equals the Cost Explorer custom range for the same month (manual).

## 7. Performance

On the mock dataset (about 6k cost rows, 25 resources), `/dashboard/overview` responds in under 150 ms and a full
180-day backfill of 3 providers completes in about 3 s on PostgreSQL.
