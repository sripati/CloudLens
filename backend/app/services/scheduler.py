"""APScheduler jobs running inside the backend process.

| Job               | Schedule                                   | What it does                                  |
|-------------------|--------------------------------------------|-----------------------------------------------|
| daily_sync        | cron DAILY_SYNC_HOUR:DAILY_SYNC_MINUTE     | re-fetch last N days of costs + inventory     |
| intraday_costs    | every INTRADAY_COST_REFRESH_MINUTES        | refresh today's running cost                  |
| metrics           | every METRICS_INTERVAL_MINUTES             | latest CPU / memory samples                   |
| alert_evaluation  | every ALERT_EVAL_INTERVAL_SECONDS          | evaluate rules, update Prometheus gauges      |
| retention         | daily 03:30                                | delete data older than retention windows     |

Run the backend with a single worker (the default in Docker) so jobs are not duplicated.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.database import SessionLocal

log = logging.getLogger("cloudlens.scheduler")
_scheduler: Optional[BackgroundScheduler] = None


def _with_session(fn: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        db = SessionLocal()
        try:
            return fn(db, *args, **kwargs)
        except Exception:
            log.exception("job %s failed", fn.__name__)
        finally:
            db.close()

    wrapper.__name__ = fn.__name__
    return wrapper


def job_daily(db):
    from app.services.ingestion import run_job

    run_job(db, "daily")


def job_intraday(db):
    from app.services.ingestion import run_job

    run_job(db, "intraday")


def job_metrics(db):
    from app.services.ingestion import run_job

    run_job(db, "metrics")


def job_alerts(db):
    from app.services.alert_engine import evaluate_all, refresh_metrics

    evaluate_all(db)
    refresh_metrics(db)


def job_retention(db):
    from app.services.ingestion import apply_retention

    log.info("retention: %s", apply_retention(db))


def job_startup(db):
    from app.services.ingestion import backfill_if_empty, run_job

    if not backfill_if_empty(db):
        run_job(db, "manual", triggered_by="startup")
    job_alerts(db)


JOBS = {
    "daily_sync": job_daily,
    "intraday_costs": job_intraday,
    "metrics": job_metrics,
    "alert_evaluation": job_alerts,
    "retention": job_retention,
}


def start() -> None:
    global _scheduler
    s = get_settings()
    if not s.SCHEDULER_ENABLED or _scheduler is not None:
        return
    sch = BackgroundScheduler(timezone=s.TIMEZONE, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    sch.add_job(_with_session(job_daily), "cron", hour=s.DAILY_SYNC_HOUR, minute=s.DAILY_SYNC_MINUTE, id="daily_sync")
    sch.add_job(_with_session(job_intraday), "interval", minutes=s.INTRADAY_COST_REFRESH_MINUTES, id="intraday_costs")
    sch.add_job(_with_session(job_metrics), "interval", minutes=s.METRICS_INTERVAL_MINUTES, id="metrics")
    sch.add_job(_with_session(job_alerts), "interval", seconds=s.ALERT_EVAL_INTERVAL_SECONDS, id="alert_evaluation")
    sch.add_job(_with_session(job_retention), "cron", hour=3, minute=30, id="retention")
    sch.start()
    _scheduler = sch
    # initial load in the background so the API is responsive immediately
    threading.Thread(target=_with_session(job_startup), name="cloudlens-startup", daemon=True).start()
    log.info("scheduler started with %d jobs", len(sch.get_jobs()))


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def jobs_info():
    if _scheduler is None:
        return []
    return [
        {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None, "trigger": str(j.trigger)}
        for j in _scheduler.get_jobs()
    ]


def run_now(job_id: str) -> bool:
    fn = JOBS.get(job_id)
    if fn is None:
        return False
    threading.Thread(target=_with_session(fn), daemon=True).start()
    return True
