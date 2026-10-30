# Future Enhancements

Ordered roughly by value versus effort. Each item names the files you would touch.

## Near term

| Enhancement | Notes / where |
|---|---|
| **Database migrations with Alembic** | Tables are currently created by `create_all`. Add `alembic init`, autogenerate from `app/models`, and run `alembic upgrade head` in the backend entrypoint. Needed before changing columns in production. |
| **HTTPS** | Caddy container in front of `frontend`, or an AWS ALB + ACM. Update `DASHBOARD_PUBLIC_URL` and `CORS_ORIGINS`. |
| **Live exchange rate** | Daily job fetching USD→INR (for example the RBI reference rate) into `app_settings.exchange_rate_inr`; keep the manual override. |
| **Per-team budgets** | New `budgets` table (scope: provider, environment, tag), so rules can reference a budget by id. Touches `settings_service.budget_for`, Settings screen. |
| **Resource-level AWS costs** | Enable Cost Explorer *hourly and resource-level data* (extra charge) or read the CUR in Athena; add `RESOURCE_ID` grouping in `aws.py`. |
| **More AWS inventory** | EKS node groups, Lambda, S3 bucket metrics (`aws.py → fetch_resources`). |
| **Alert silencing from the UI** | Call the Alertmanager API `/api/v2/silences` from a new endpoint; add a "Snooze 24h" button in the Alerts screen. |

## Medium term

| Enhancement | Notes |
|---|---|
| **Worker separation** | Move APScheduler jobs into a `worker` service (same image, `python -m app.worker`) so the API can scale to several replicas. |
| **Partitioning** | Partition `cost_records` by month (PostgreSQL declarative partitioning) or adopt TimescaleDB hypertables for `resource_metrics`. |
| **ML forecasting** | Replace the 7-day-average forecast with Prophet/ARIMA in `analytics.month_to_date`; show confidence bands. |
| **Anomaly detection per service** | Run `anomalies` per service and environment, using z-score or seasonal decomposition. |
| **SSO** | OIDC (Azure AD / Google Workspace) via `authlib`; map groups to roles. |
| **Audit log** | Table recording who changed which rule or setting; show it in the Users screen. |
| **Scheduled email reports** | Weekly PDF of the Reports screen to finance (WeasyPrint + SMTP/SES). |
| **Kubernetes cost allocation** | Integrate OpenCost/Kubecost to split cluster cost by namespace. |

## Long term

- Multi-tenant SaaS mode (organisation id on every table, row-level security).
- Automated remediation: one-click "stop idle instance" with an approval workflow (needs write IAM permissions).
- Commitment planning: Savings Plans / Reserved Instance coverage and recommendations from the CE APIs.
- Carbon footprint view (AWS Customer Carbon Footprint Tool, GCP Carbon Footprint export).

## How to add a new cloud provider (for example Oracle Cloud)

1. Create `backend/app/services/providers/oci.py` implementing `CloudProvider`
   (`is_configured`, `account_id`, `fetch_costs`, `fetch_resources`, `fetch_metrics`, `test_connection`).
2. Return `CostItem` objects using `classify_service` / `normalize_environment` from `normalizer.py`.
3. Register it in `providers/__init__.py → get_provider`, add `"oci"` to `normalizer.PROVIDERS`.
4. Add mock assets in `providers/mock.py → CATALOG["oci"]` and `ACCOUNTS`.
5. Frontend: add to `utils/constants.js → PROVIDERS` and a colour token `--oci` in `styles/theme.css`.
6. Add parser unit tests in `tests/test_providers.py`.
