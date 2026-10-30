# Module: Scheduler

**Path:** `backend/app/services/scheduler.py`

APScheduler `BackgroundScheduler` running inside the FastAPI process (started in `main.lifespan`).

| Job id | Trigger | Function | Purpose |
|---|---|---|---|
| `daily_sync` | cron `DAILY_SYNC_HOUR:DAILY_SYNC_MINUTE` (02:00 IST) | `job_daily` | Re-fetch the last 3 days of costs + inventory + metrics |
| `intraday_costs` | every `INTRADAY_COST_REFRESH_MINUTES` | `job_intraday` | Today's running cost |
| `metrics` | every `METRICS_INTERVAL_MINUTES` | `job_metrics` | Latest utilization samples |
| `alert_evaluation` | every `ALERT_EVAL_INTERVAL_SECONDS` | `job_alerts` | `evaluate_all` + `refresh_metrics` |
| `retention` | cron 03:30 | `job_retention` | Delete old data |

Defaults: `coalesce=True` (missed runs collapse into one), `max_instances=1` (no overlap), and
`misfire_grace_time=300`. Timezone is `TIMEZONE`.

**Startup:** a background thread runs `job_startup`: backfill if the DB is empty, otherwise a quick
manual sync, then alert evaluation. The API is usable immediately.

**Utilities:** `jobs_info()` (shown on Cloud Accounts), `run_now(job_id)`, `shutdown()`.

**Important:** run exactly **one** backend process (`--workers 1`, one replica), or jobs will run
several times. To scale the API, move the scheduler into a separate worker container. See
[future-enhancements.md](../future-enhancements.md).

Disable it with `SCHEDULER_ENABLED=false` (done in tests).
