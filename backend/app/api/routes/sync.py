import threading
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models import SyncRun, User
from app.schemas import MockAnomaly, SyncRequest
from app.services import cloud_accounts, scheduler, settings_service
from app.services.ingestion import local_today, run_job
from app.services.providers import connectors_for

router = APIRouter(prefix="/sync", tags=["sync"])


def _run_dict(r: SyncRun) -> dict:
    return {
        "id": r.id, "provider": r.provider, "job": r.job, "data_source": r.data_source, "environment": r.environment, "status": r.status,
        "triggered_by": r.triggered_by, "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None, "cost_records": r.cost_records,
        "resources": r.resources, "metric_samples": r.metric_samples, "api_calls": r.api_calls, "error": r.error,
    }


def _latest_run(db: Session, name: str, environment: str, source: str = "live") -> Optional[dict]:
    run = db.execute(
        select(SyncRun).where(SyncRun.provider == name, SyncRun.environment == environment, SyncRun.data_source == source).order_by(SyncRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()
    return _run_dict(run) if run else None


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = get_settings()
    source = cloud_accounts.summary(db)
    providers = []
    for name in ["aws", "azure", "gcp"]:
        enabled = name in s.enabled_providers
        mode = cloud_accounts.mode_of(db, name)
        connections = cloud_accounts.connection_summaries(db, name)
        for c in connections:
            c["last_run"] = _latest_run(db, name, c["environment"])
        # when Live, a failing connection must not be hidden by a healthy one that ran later
        latest = [c["last_run"] for c in connections if c["last_run"]] if mode == "live" else []
        failing = [r for r in latest if r["status"] in ("failed", "skipped")]
        if mode == "mock":
            last_run = _latest_run(db, name, "", "mock")
            account = connectors_for(name, db)[0].account_id()
        else:
            last_run = (failing or sorted(latest, key=lambda r: r["started_at"], reverse=True) or [None])[0]
            account = ", ".join(c["account"] for c in connections if c["account"])
        last_ok = db.execute(select(SyncRun).where(SyncRun.provider == name, SyncRun.data_source == mode, SyncRun.status == "success").order_by(SyncRun.started_at.desc()).limit(1)).scalar_one_or_none()
        providers.append({
            "provider": name,
            "enabled": enabled,
            "configured": mode == "mock" or bool(connections),
            "verified": any(c["verified"] for c in connections),
            "mode": mode,
            "connections": connections,
            "account_id": account or None,
            "last_run": last_run,
            "last_success_at": last_ok.finished_at.isoformat() if last_ok and last_ok.finished_at else None,
        })
    return {
        "data_source": source,
        "alert_delivery": s.ALERT_DELIVERY,
        "providers": providers,
        "jobs": scheduler.jobs_info(),
        "mock_anomalies": settings_service.get_value(db, "mock_anomalies") if source != "live" else [],
    }


@router.get("/runs")
def runs(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [_run_dict(r) for r in db.execute(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(min(limit, 500))).scalars().all()]


@router.post("/run", status_code=202)
def trigger(body: SyncRequest, _: User = Depends(require_admin)):
    """Start a sync in the background and return immediately."""
    def work():
        db = SessionLocal()
        try:
            run_job(db, body.job, triggered_by="manual", providers=body.providers)
            from app.services.alert_engine import evaluate_all, refresh_metrics

            evaluate_all(db)
            refresh_metrics(db)
        finally:
            db.close()

    threading.Thread(target=work, daemon=True).start()
    return {"accepted": True, "job": body.job, "providers": body.providers or get_settings().enabled_providers}


@router.post("/test/{provider}")
def test_connection(provider: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if provider not in ("aws", "azure", "gcp"):
        raise HTTPException(404, "Unknown provider")
    connectors = connectors_for(provider, db)
    if connectors and connectors[0].source == "mock":
        return {"provider": provider, **connectors[0].test_connection(), "api_calls": 0}
    checks, failures, accounts = [], [], []
    for p in connectors:  # re-test every saved environment, recording each result
        label = p.environment.title()
        result = p.test_connection()
        cloud_accounts.record_test(db, provider, p.environment, p.c, result)
        checks += [{**c, "name": f"{label}: {c['name']}"} for c in result.get("checks", [])]
        if result["ok"]:
            accounts.append(str(result.get("account")))
        else:
            failures.append(f"{label}: {result['message']}")
    return {
        "provider": provider, "ok": bool(connectors) and not failures, "checks": checks, "account": ", ".join(accounts),
        "message": "; ".join(failures) or f"{len(connectors)} connection(s) validated", "api_calls": sum(p.api_calls for p in connectors),
    }


@router.post("/mock/anomaly")
def inject_anomaly(body: MockAnomaly, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Demo helper (clouds in mock mode only): multiply a provider's cost on a given day, then re-sync it."""
    if cloud_accounts.mode_of(db, body.provider) != "mock":
        raise HTTPException(400, f"{body.provider} is not in Mock mode")
    day = (local_today() - timedelta(days=body.days_ago)).isoformat()
    items = [a for a in (settings_service.get_value(db, "mock_anomalies") or []) if not (a["provider"] == body.provider and a["date"] == day)]
    items.append({"provider": body.provider, "date": day, "factor": body.factor})
    settings_service.set_value(db, "mock_anomalies", items)
    _resync_day(db, body.provider, body.days_ago)
    return {"injected": items[-1]}


@router.delete("/mock/anomaly")
def clear_anomalies(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    items = settings_service.get_value(db, "mock_anomalies") or []
    settings_service.set_value(db, "mock_anomalies", [])
    for a in items:
        days_ago = (local_today() - date.fromisoformat(a["date"])).days
        _resync_day(db, a["provider"], days_ago)
    return {"cleared": len(items)}


def _resync_day(db: Session, provider: str, days_ago: int) -> None:
    from app.services.alert_engine import evaluate_all
    from app.services.ingestion import sync_provider
    from app.services.providers.mock import MockProvider

    day = local_today() - timedelta(days=days_ago)
    overrides = settings_service.get_value(db, "mock_anomalies") or []
    # always the mock rows, even if the cloud has since moved to Live
    sync_provider(db, provider, MockProvider(provider, overrides=overrides), job="manual", cost_start=day, cost_end=day + timedelta(days=1), triggered_by="manual")
    evaluate_all(db)
