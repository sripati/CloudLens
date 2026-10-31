import hmac
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AlertEvent, AlertRule, User
from app.models.alert import ALERT_METRICS
from app.schemas import AlertEventOut, AlertRuleIn, AlertRuleOut, TestNotification
from app.services import alert_engine, notifier, settings_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/metrics")
def metric_catalog(_: User = Depends(get_current_user)):
    return [{"key": k, "label": v, "unit": alert_engine.UNITS.get(k, "")} for k, v in ALERT_METRICS.items()]


@router.get("/rules", response_model=list[AlertRuleOut])
def list_rules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.execute(select(AlertRule).order_by(AlertRule.id)).scalars().all()


@router.post("/rules", response_model=AlertRuleOut, status_code=201)
def create_rule(body: AlertRuleIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rule = AlertRule(**body.model_dump(), created_by=admin.id)
    db.add(rule)
    db.commit()
    alert_engine.evaluate_all(db)
    db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, body: AlertRuleIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(rule, k, v)
    db.commit()
    alert_engine.evaluate_all(db)
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()


@router.post("/evaluate")
def evaluate(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Evaluate all rules now (normally runs every ALERT_EVAL_INTERVAL_SECONDS)."""
    return alert_engine.evaluate_all(db)


@router.get("/events", response_model=list[AlertEventOut])
def list_events(
    status: Optional[str] = Query(None, pattern="^(firing|resolved)$"),
    severity: Optional[str] = Query(None, pattern="^(critical|warning|info)$"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(limit)
    if status:
        q = q.where(AlertEvent.status == status)
    if severity:
        q = q.where(AlertEvent.severity == severity)
    return db.execute(q).scalars().all()


@router.post("/events/{event_id}/ack", response_model=AlertEventOut)
def acknowledge(event_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ev = db.get(AlertEvent, event_id)
    if ev is None:
        raise HTTPException(404, "Event not found")
    ev.acknowledged = True
    db.commit()
    return ev


@router.post("/test", response_model=AlertEventOut)
def test_notification(body: TestNotification, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    channels = notifier.resolve_channels(body.channel, settings_service.get_value(db, "notification_channel"))
    now = datetime.now(timezone.utc)
    status_sent, err = notifier.send(channels, "Test notification", body.message, "info", "firing", {"Sent by": "CloudLens admin", "Time": now.strftime("%Y-%m-%d %H:%M UTC")}, settings_service.webhook_urls(db))
    ev = AlertEvent(
        fingerprint=f"test-{now.timestamp():.0f}", status="firing", severity="info", title="Test notification", message=body.message,
        source="test", starts_at=now, notified_channels=",".join(channels), notification_status=status_sent, notification_error=err, labels={},
    )
    db.add(ev)
    db.commit()
    return ev


@router.post("/webhook", include_in_schema=True)
async def alertmanager_webhook(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Receiver for Prometheus Alertmanager (webhook_configs). Protected by a shared bearer token."""
    expected = f"Bearer {get_settings().ALERTMANAGER_WEBHOOK_TOKEN}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "Invalid webhook token")
    payload = await request.json()
    ids = alert_engine.handle_alertmanager(db, payload)
    return {"received": len(payload.get("alerts", [])), "events_created": ids}
