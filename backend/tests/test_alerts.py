from sqlalchemy import select

from app.models import AlertEvent, AlertRule
from app.services import alert_engine, notifier, prom_metrics


def _rule(db, **kw):
    r = AlertRule(**{"name": "t", "metric": "mtd_cost", "operator": ">", "threshold": 1, "severity": "warning", **kw})
    db.add(r)
    db.commit()
    return r


def test_seeded_rules_present(db):
    names = {r.name for r in db.execute(select(AlertRule)).scalars()}
    assert "Monthly budget 80% used" in names and "Idle resources detected" in names


def test_rule_fires_and_resolves_in_direct_mode(db, fake_notifier):
    rule = _rule(db, name="test-mtd", metric="mtd_cost", threshold=1)
    alert_engine.evaluate_all(db)
    db.refresh(rule)
    assert rule.state == "firing" and rule.last_value > 1
    fired = [s for s in fake_notifier if s["title"] == "test-mtd" and s["status"] == "firing"]
    assert fired and fired[0]["channels"] == ["slack", "teams"]
    # raise threshold -> resolved notification
    rule.threshold = 10**12
    db.commit()
    alert_engine.evaluate_all(db)
    db.refresh(rule)
    assert rule.state == "ok"
    assert any(s["title"] == "test-mtd" and s["status"] == "resolved" for s in fake_notifier)
    db.delete(rule)
    db.commit()


def test_operators_and_metrics(db):
    for metric in ("daily_cost", "budget_used_pct", "forecast_budget_pct", "cost_anomaly_pct", "resource_cpu", "resource_memory", "idle_resource_count"):
        r = _rule(db, name=f"m-{metric}", metric=metric, operator=">=", threshold=0)
        value, detail = alert_engine.compute_value(db, r)
        assert detail
        if metric != "cost_anomaly_pct":
            assert value is not None, metric
        db.delete(r)
    db.commit()


def test_scope_filters_apply(db):
    all_r = _rule(db, name="all", metric="daily_cost")
    aws_r = _rule(db, name="aws", metric="daily_cost", provider="aws")
    v_all, _ = alert_engine.compute_value(db, all_r)
    v_aws, _ = alert_engine.compute_value(db, aws_r)
    assert 0 < v_aws < v_all
    db.delete(all_r)
    db.delete(aws_r)
    db.commit()


def test_prometheus_gauges_exported(db):
    alert_engine.evaluate_all(db)
    alert_engine.refresh_metrics(db)
    from prometheus_client import generate_latest

    text = generate_latest(prom_metrics.REGISTRY).decode()
    assert "cloudlens_alert_rule_breached" in text
    assert 'cloudlens_cost_mtd_usd{provider="aws"}' in text
    assert "cloudlens_resource_cpu_percent" in text


def test_alertmanager_webhook_creates_event_once(db, fake_notifier):
    rule = db.execute(select(AlertRule).where(AlertRule.name == "Idle resources detected")).scalar_one()
    payload = {
        "version": "4", "status": "firing", "receiver": "cloudlens",
        "alerts": [{
            "status": "firing", "fingerprint": "abc123",
            "labels": {"alertname": "CloudLensRuleBreached", "rule_id": str(rule.id), "severity": "info"},
            "annotations": {"summary": "x"}, "startsAt": "2026-10-29T10:00:00Z", "endsAt": "0001-01-01T00:00:00Z",
        }],
    }
    ids = alert_engine.handle_alertmanager(db, payload)
    assert len(ids) == 1
    assert alert_engine.handle_alertmanager(db, payload) == []  # duplicate ignored
    ev = db.get(AlertEvent, ids[0])
    assert ev.rule_id == rule.id and ev.source == "alertmanager" and ev.notification_status == "sent"
    payload["alerts"][0]["status"] = "resolved"
    payload["alerts"][0]["endsAt"] = "2026-10-29T11:00:00Z"
    assert len(alert_engine.handle_alertmanager(db, payload)) == 1


def test_generic_alert_without_rule(db):
    payload = {"alerts": [{"status": "firing", "labels": {"alertname": "CloudLensSyncFailing", "severity": "critical", "provider": "aws"},
                           "annotations": {"summary": "Sync failing", "description": "AWS sync failed"}, "startsAt": "2026-10-29T09:00:00Z"}]}
    ids = alert_engine.handle_alertmanager(db, payload)
    ev = db.get(AlertEvent, ids[0])
    assert ev.title == "Sync failing" and ev.severity == "critical" and ev.rule_id is None


def test_channel_resolution():
    assert notifier.resolve_channels("default", "teams") == ["teams"]
    assert notifier.resolve_channels("both", "slack") == ["slack", "teams"]
    assert notifier.resolve_channels("slack", "both") == ["slack"]
    assert notifier.resolve_channels(None, "both") == ["slack", "teams"]


def test_payload_shapes():
    s = notifier.slack_payload("Budget", "msg", "critical", "firing", {"A": "1"})
    assert s["text"].startswith("[CRITICAL]") and s["blocks"][0]["type"] == "header"
    t = notifier.teams_payload("Budget", "msg", "warning", "resolved", {"A": "1"})
    card = t["attachments"][0]
    assert card["contentType"] == "application/vnd.microsoft.card.adaptive"
    assert card["content"]["body"][0]["text"].startswith("RESOLVED")
