import threading
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.models import SyncRun, User
from app.schemas import MockAnomaly, SyncRequest
from app.services import scheduler, settings_service
from app.services.ingestion import local_today, run_job
from app.services.providers import get_provider

router = APIRouter(prefix="/sync", tags=["sync"])


def _run_dict(r: SyncRun) -> dict:
    return {
        "id": r.id, "provider": r.provider, "job": r.job, "data_source": r.data_source, "status": r.status,
        "triggered_by": r.triggered_by, "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None, "cost_records": r.cost_records,
        "resources": r.resources, "metric_samples": r.metric_samples, "api_calls": r.api_calls, "error": r.error,
    }


@router.get("/status")
def status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = get_settings()
    providers = []
    for name in ["aws", "azure", "gcp"]:
        enabled = name in s.enabled_providers
        last = db.execute(select(SyncRun).where(SyncRun.provider == name).order_by(SyncRun.started_at.desc()).limit(1)).scalar_one_or_none()
        last_ok = db.execute(select(SyncRun).where(SyncRun.provider == name, SyncRun.status == "success").order_by(SyncRun.started_at.desc()).limit(1)).scalar_one_or_none()
        p = get_provider(name, db)
        providers.append({
            "provider": name,
            "enabled": enabled,
            "configured": p.is_configured(),
            "mode": s.DATA_SOURCE,
            # avoid an STS call for AWS on every page load in live mode
            "account_id": (p.account_id() if (s.DATA_SOURCE == "mock" or name != "aws") and p.is_configured() else None),
            "last_run": _run_dict(last) if last else None,
            "last_success_at": last_ok.finished_at.isoformat() if last_ok and last_ok.finished_at else None,
        })
    return {
        "data_source": s.DATA_SOURCE,
        "alert_delivery": s.ALERT_DELIVERY,
        "providers": providers,
        "jobs": scheduler.jobs_info(),
        "mock_anomalies": settings_service.get_value(db, "mock_anomalies") if s.DATA_SOURCE == "mock" else [],
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
    p = get_provider(provider, db)
    return {"provider": provider, **p.test_connection(), "api_calls": p.api_calls}


@router.post("/mock/anomaly")
def inject_anomaly(body: MockAnomaly, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Demo helper (mock mode only): multiply a provider's cost on a given day, then re-sync it."""
    if get_settings().DATA_SOURCE != "mock":
        raise HTTPException(400, "Only available when DATA_SOURCE=mock")
    day = (local_today() - timedelta(days=body.days_ago)).isoformat()
    items = [a for a in (settings_service.get_value(db, "mock_anomalies") or []) if not (a["provider"] == body.provider and a["date"] == day)]
    items.append({"provider": body.provider, "date": day, "factor": body.factor})
    settings_service.set_value(db, "mock_anomalies", items)
    _resync_day(db, body.provider, body.days_ago)
    return {"injected": items[-1]}


@router.delete("/mock/anomaly")
def clear_anomalies(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if get_settings().DATA_SOURCE != "mock":
        raise HTTPException(400, "Only available when DATA_SOURCE=mock")
    items = settings_service.get_value(db, "mock_anomalies") or []
    settings_service.set_value(db, "mock_anomalies", [])
    for a in items:
        days_ago = (local_today() - date.fromisoformat(a["date"])).days
        _resync_day(db, a["provider"], days_ago)
    return {"cleared": len(items)}


def _resync_day(db: Session, provider: str, days_ago: int) -> None:
    from app.services.alert_engine import evaluate_all
    from app.services.ingestion import sync_provider

    day = local_today() - timedelta(days=days_ago)
    sync_provider(db, provider, get_provider(provider, db), job="manual", cost_start=day, cost_end=day + timedelta(days=1), triggered_by="manual")
    evaluate_all(db)
