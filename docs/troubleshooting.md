# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose up` fails: *set POSTGRES_PASSWORD in .env* | `.env` missing | `cp .env.example .env` and set the password |
| Backend build fails at `pip install` with *exit code: 2* | Network timeout or reset while pip downloads (usually the large Azure/Google SDKs) | Run `docker compose build backend` again; the pip cache keeps finished downloads. For mock mode, set `INSTALL_CLOUD_SDKS=false` in `.env` to skip the SDKs. On a VPN or corporate proxy, try off the VPN. |
| Dashboard shows "Loading…" forever / 502 | Backend not up yet or crashed | `docker compose logs backend`; wait for `CloudLens started`; check `DATABASE_URL` |
| Login says *Incorrect email or password* | Users were created with older `.env` values | Users are only seeded when the table is empty. Reset with `docker compose exec db psql -U cloudlens -c "DELETE FROM users;"` and restart the backend |
| `value is not a valid email address` on login | Very old build that used `.local` domains | Use a real-looking domain such as `admin@cloudlens.dev` |
| All charts empty | Backfill not finished or `DATA_SOURCE=live` with no credentials | Check Cloud Accounts → Sync history; status *skipped* means credentials are missing |
| Provider shows *skipped* | Live mode without credentials for that provider | Fill in its `.env` section or remove it from `ENABLED_PROVIDERS` |
| AWS: `AccessDeniedException` on `ce:GetCostAndUsage` | Policy missing or Cost Explorer not enabled | Attach `deploy/aws/iam-policy.json`; enable Cost Explorer (it takes up to 24 h) |
| AWS: every cost in environment *unassigned* | Cost allocation tag not activated | Billing → Cost allocation tags → activate `environment` (it applies to new data only) |
| Azure: `AuthorizationFailed` | Service principal lacks a role | Assign *Cost Management Reader*, *Monitoring Reader* and *Reader* on the subscription |
| Azure: HTTP 429 | Cost Management throttling | Increase `INTRADAY_COST_REFRESH_MINUTES`; daily sync is fine |
| GCP: `Not found: Table` | Wrong `GCP_BILLING_EXPORT_TABLE` | Copy the full `project.dataset.table` name from BigQuery |
| GCP: `bytes billed exceeds limit` | Very large export table | The 2 GB guard stopped the query; reduce `SYNC_LOOKBACK_DAYS` or raise the limit in `gcp.py` |
| No Slack / Teams messages | Webhook URL wrong, or still pointing at the mock | Alerts → Test notification, then check Event history → *Delivery* column for the HTTP error |
| Rules show *Firing* but no message arrives | Alertmanager cannot reach the backend, or the token doesn't match | `docker compose logs alertmanager`; `ALERTMANAGER_WEBHOOK_TOKEN` must match for both services (same `.env`) |
| Prometheus target `cloudlens-backend` DOWN | Backend unhealthy | `curl localhost:8000/health`; check DB connectivity |
| Same alert repeated every 4 h | Alertmanager `repeat_interval` | Expected while the condition persists; silence it in Alertmanager or raise the threshold |
| Times look off by 5:30 h | Timezone | `TIMEZONE=Asia/Kolkata` controls day boundaries; the DB stores UTC |
| Scheduled jobs run twice | More than one backend worker or replica | Keep `--workers 1` and one backend container |
| Frontend build OOM on EC2 | 2 GB RAM | The user-data script adds 2 GB swap; or build the images locally and push them to a registry |
| INR amounts wrong | Exchange rate | Settings → Exchange rate (INR per USD) |

## Diagnostic commands

```bash
docker compose ps
docker compose logs --tail=200 backend
curl -s localhost:8000/health
curl -s localhost:8000/metrics | grep cloudlens_alert_rule_breached
curl -s localhost:9090/api/v1/alerts | jq .
curl -s localhost:9000/messages | jq '.[0]'          # mock inbox
docker compose exec db psql -U cloudlens -c "SELECT provider, job, status, error FROM sync_runs ORDER BY id DESC LIMIT 10;"
```
