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
| Backend on SQLite | 84 | **84 passed** |
| Backend on PostgreSQL 16 | 84 | **84 passed** |
| Backend with pinned `requirements*.txt` in a clean virtualenv | 84 | **84 passed** |
| Frontend (vitest) | 31 | **31 passed** |
| Frontend production build | — | success (no warnings) |
| promtool check rules / config | 5 rules | SUCCESS |
| amtool check-config | — | SUCCESS |
| docker compose config | — | valid |

Backend line coverage: **85 %** overall (analytics 97 %, alert engine 95 %, ingestion 83 %).
The live connectors are about 47 % covered. Their parsing logic is fully tested, while the remaining lines are
SDK calls that need real cloud accounts and are verified with **Cloud Accounts → Test connection**.

### Backend test inventory

| File | Tests | Highlights |
|---|---|---|
| `test_normalizer.py` | 30 | 16 service names across 3 clouds → type; 12 environment spellings; region; INR/GCP conversion |
| `test_providers.py` | 10 | Mock determinism, partial today, anomaly cycles, overrides, metric bounds; AWS/Azure/GCP parsers; unconfigured live providers; AWS Stubber pagination |
| `test_ingestion_analytics.py` | 15 | Backfill of 3 providers / 25 resources; re-sync idempotent; duplicate merge; skipped provider; **breakdowns sum to the total** for 4 dimensions; daily series = total; filters narrow; budget scope; MoM; injected anomaly detected; statuses and recommendations; utilization; drill-down |
| `test_alerts.py` | 9 | Seeded rules; fire → resolve notifications; all 8 metric types compute; provider scope; Prometheus exposition; webhook dedupe and resolve; generic alerts; channels; payload formats |
| `test_api.py` | 20 | Health/metrics; 401s; me; overview shape; 422 validation; costs, resources, reports endpoints; **RBAC 403 for viewer**; rule CRUD with live evaluation; test notification + ack; webhook token; settings round trip; user management guards; sync status and mock anomaly |

### Date-range tests (added with the calendar picker)

| Where | What is checked |
|---|---|
| `test_api.py::test_future_dates_rejected` | Future `end` or `start` → 422 with a readable message on dashboard, costs, reports and resources; a future month for `/reports/monthly` → 422 |
| `test_api.py::test_start_after_end_and_max_span` | start > end → 422; 732 days → 422; exactly 731 days and a single day are accepted |
| `test_api.py::test_date_bounds` | `/costs/date-bounds` returns today, first data date and the 731-day limit |
| `test_api.py::test_monthly_follows_selected_range` | Monthly view uses the selected range; partial first month; run-rate comparison; months sum to the period total |
| `test_api.py::test_range_report_six_months` | Range report: monthly breakdown, pro-rated budget, totals match, CSV name and content |
| `test_ingestion_analytics.py` | `month_spans` (partial / full / in progress), `extend_history` fills older days once |
| `utils/dates.test.js` (14) | Presets computed from today and moving with it, clamping to data start, stored-range fallback, every validation message |
| `DateRangePicker.test.jsx` (8) | Trigger label, one-click preset, click-start/click-end + Apply, restart when clicking before start, disabled future, typed-date errors, Escape cancels, keyboard navigation never enters the future |

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
| UI-07 | Custom range | Date button → click a start day, click an end day → Apply | Charts, KPIs and subtitles cover exactly that range; button shows *Custom range* with dates and day count |
| UI-07a | Preset range | Date button → *Last 6 months* | Applies in one click; range ends today and starts on the 1st of the month 5 months ago |
| UI-07b | Future date | Type a To date after today | Red message *End date can’t be in the future*, Apply disabled; future days are disabled in the calendar |
| UI-07c | Start after end | Type From later than To | Message *Start date must be on or before the end date*, Apply disabled |
| UI-07d | Too long | Range over 731 days | Message with the day count, Apply disabled |
| UI-07e | Six-month report | Reports → *Last 6 months* → Download CSV | Monthly breakdown for 6 months; CSV `cloudlens_report_<start>_to_<end>.csv` |
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
