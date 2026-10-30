API = "/api/v1"


def test_health_and_metrics(client):
    assert client.get("/health").json()["database"] is True
    assert "cloudlens_http_requests_total" in client.get("/metrics").text


def test_login_failures(client):
    assert client.post(f"{API}/auth/login", json={"email": "admin@test.dev", "password": "wrong"}).status_code == 401
    assert client.get(f"{API}/dashboard/summary").status_code == 401
    assert client.get(f"{API}/dashboard/summary", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_me(client, admin_headers, viewer_headers):
    assert client.get(f"{API}/auth/me", headers=admin_headers).json()["role"] == "admin"
    assert client.get(f"{API}/auth/me", headers=viewer_headers).json()["role"] == "viewer"


def test_dashboard_overview(client, viewer_headers):
    r = client.get(f"{API}/dashboard/overview", params={"days": 30}, headers=viewer_headers)
    assert r.status_code == 200
    body = r.json()
    for key in ("summary", "trend", "by_provider", "by_resource_type", "utilization", "top_resources", "recent_alerts"):
        assert key in body
    assert len(body["trend"]["points"]) == 30
    assert len(body["top_resources"]) == 8


def test_filters_validation(client, viewer_headers):
    assert client.get(f"{API}/dashboard/summary", params={"provider": "oracle"}, headers=viewer_headers).status_code == 422
    assert client.get(f"{API}/dashboard/summary", params={"start": "2026-10-10", "end": "2026-10-01"}, headers=viewer_headers).status_code == 422
    r = client.get(f"{API}/dashboard/summary", params={"provider": "aws,gcp", "environment": "production", "days": 7}, headers=viewer_headers)
    assert r.status_code == 200 and r.json()["filters"]["providers"] == ["aws", "gcp"]


def test_cost_endpoints(client, viewer_headers):
    h = viewer_headers
    assert client.get(f"{API}/costs/daily", params={"group_by": "environment", "days": 14}, headers=h).json()["group_by"] == "environment"
    assert client.get(f"{API}/costs/daily", params={"group_by": "bogus"}, headers=h).status_code == 422
    assert client.get(f"{API}/costs/breakdown", params={"dimension": "service"}, headers=h).json()["rows"]
    assert len(client.get(f"{API}/costs/monthly", params={"months": 3}, headers=h).json()["months"]) == 3
    assert "aws" in client.get(f"{API}/costs/filters", headers=h).json()["providers"]
    csv = client.get(f"{API}/costs/export", params={"days": 2}, headers=h)
    assert csv.status_code == 200 and csv.text.startswith("date,provider")


def test_resources_endpoints(client, viewer_headers):
    h = viewer_headers
    rows = client.get(f"{API}/resources", params={"status": "idle"}, headers=h).json()
    assert rows and all(r["status"] == "idle" for r in rows)
    assert client.get(f"{API}/resources/{rows[0]['id']}", headers=h).status_code == 200
    assert client.get(f"{API}/resources/99999", headers=h).status_code == 404
    assert client.get(f"{API}/resources/recommendations", headers=h).json()["total_monthly_savings"] > 0
    assert client.get(f"{API}/resources/utilization", params={"hours": 24}, headers=h).status_code == 200


def test_rbac_viewer_cannot_write(client, viewer_headers):
    h = viewer_headers
    rule = {"name": "Viewer rule", "metric": "daily_cost", "operator": ">", "threshold": 1}
    assert client.post(f"{API}/alerts/rules", json=rule, headers=h).status_code == 403
    assert client.put(f"{API}/settings", json={"exchange_rate_inr": 90}, headers=h).status_code == 403
    assert client.get(f"{API}/users", headers=h).status_code == 403
    assert client.post(f"{API}/sync/run", json={"job": "manual"}, headers=h).status_code == 403
    assert client.post(f"{API}/alerts/test", json={}, headers=h).status_code == 403


def test_alert_rule_crud(client, admin_headers):
    h = admin_headers
    bad = client.post(f"{API}/alerts/rules", json={"name": "Bad", "metric": "nope", "threshold": 1}, headers=h)
    assert bad.status_code == 422
    r = client.post(f"{API}/alerts/rules", json={"name": "API rule", "metric": "daily_cost", "provider": "azure", "operator": ">", "threshold": 1, "severity": "critical", "channels": "teams"}, headers=h)
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["state"] == "firing" and rule["last_value"] > 1
    rule["threshold"] = 10**9
    upd = client.put(f"{API}/alerts/rules/{rule['id']}", json=rule, headers=h)
    assert upd.json()["state"] == "ok"
    assert client.delete(f"{API}/alerts/rules/{rule['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/alerts/metrics", headers=h).json()


def test_test_notification_and_events(client, admin_headers, fake_notifier):
    r = client.post(f"{API}/alerts/test", json={"channel": "slack"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["notified_channels"] == "slack"
    events = client.get(f"{API}/alerts/events", headers=admin_headers).json()
    assert events and events[0]["source"] == "test"
    ack = client.post(f"{API}/alerts/events/{events[0]['id']}/ack", headers=admin_headers)
    assert ack.json()["acknowledged"] is True


def test_webhook_requires_token(client):
    payload = {"alerts": []}
    assert client.post(f"{API}/alerts/webhook", json=payload).status_code == 401
    assert client.post(f"{API}/alerts/webhook", json=payload, headers={"Authorization": "Bearer test-token"}).json()["received"] == 0


def test_settings_roundtrip(client, admin_headers, viewer_headers):
    r = client.put(f"{API}/settings", json={"exchange_rate_inr": 85.5, "notification_channel": "teams"}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["exchange_rate_inr"] == 85.5
    assert client.get(f"{API}/settings", headers=viewer_headers).json()["notification_channel"] == "teams"
    assert client.put(f"{API}/settings", json={"exchange_rate_inr": -1}, headers=admin_headers).status_code == 422
    client.put(f"{API}/settings", json={"exchange_rate_inr": 84.2, "notification_channel": "both"}, headers=admin_headers)


def test_user_management(client, admin_headers):
    h = admin_headers
    r = client.post(f"{API}/users", json={"email": "new@test.dev", "full_name": "New", "password": "Password1", "role": "viewer"}, headers=h)
    assert r.status_code == 201
    uid = r.json()["id"]
    assert client.post(f"{API}/users", json={"email": "new@test.dev", "password": "Password1"}, headers=h).status_code == 409
    assert client.patch(f"{API}/users/{uid}", json={"role": "admin"}, headers=h).json()["role"] == "admin"
    me = client.get(f"{API}/auth/me", headers=h).json()
    assert client.delete(f"{API}/users/{me['id']}", headers=h).status_code == 400
    assert client.delete(f"{API}/users/{uid}", headers=h).status_code == 204


def test_sync_status_and_mock_anomaly(client, admin_headers):
    h = admin_headers
    st = client.get(f"{API}/sync/status", headers=h).json()
    assert st["data_source"] == "mock" and len(st["providers"]) == 3
    assert client.post(f"{API}/sync/test/aws", headers=h).json()["ok"] is True
    inj = client.post(f"{API}/sync/mock/anomaly", json={"provider": "azure", "factor": 3, "days_ago": 3}, headers=h)
    assert inj.status_code == 200
    assert client.delete(f"{API}/sync/mock/anomaly", headers=h).json()["cleared"] == 1
    assert client.get(f"{API}/sync/runs", headers=h).json()


def test_reports(client, viewer_headers):
    r = client.get(f"{API}/reports/monthly", headers=viewer_headers).json()
    assert r["total"] > 0 and r["by_provider"]
    assert client.get(f"{API}/reports/monthly", params={"month": "bad"}, headers=viewer_headers).status_code == 422
    assert "Recommendations" in client.get(f"{API}/reports/monthly.csv", headers=viewer_headers).text
