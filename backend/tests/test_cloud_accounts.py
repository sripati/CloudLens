"""Per-cloud Mock / Live mode, per-environment connections, webhooks, and credential handling."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.crypto import CredentialsUnreadable, decrypt_secrets, encrypt_secrets
from app.models import CloudAccount, CloudConnection, CostRecord, Resource, SyncRun
from app.services import analytics, cloud_accounts, settings_service
from app.services.analytics import Filters
from app.services.ingestion import load_active, local_today, run_job, upsert_costs, upsert_resources
from app.services.providers import base as provider_base
from app.services.providers.aws import AWSProvider, cost_explorer_period
from app.services.providers.base import CostItem, ResourceItem

API = "/api/v1"
AWS_FORM = {
    "auth_method": "access_keys", "access_key_id": "AKIAABCDEFGHIJKLMNOP", "secret_access_key": "super-secret-value",
    "regions": "ap-south-1", "cost_explorer_region": "us-east-1",
}
ACCOUNTS = {"AKIAABCDEFGHIJKLMNOP": "111111111111", "AKIASTAGINGSTAGINGST": "222222222222"}
STAGING_FORM = {**AWS_FORM, "access_key_id": "AKIASTAGINGSTAGINGST", "secret_access_key": "staging-secret"}


class FakeLive(provider_base.CloudProvider):
    """A Live connector with no network: its account follows the access key, as a real one would."""

    name = "aws"
    display_name = "Fake"

    def __init__(self, config, ok=True, cost=7.0):
        super().__init__()
        self.c, self.ok, self.cost = config or {}, ok, cost
        self.environment = self.c.get("environment", "")

    def is_configured(self):
        return True

    def account_id(self):
        return ACCOUNTS.get(self.c.get("access_key_id"), "999988887777")

    def fetch_costs(self, start, end):
        d = local_today() - timedelta(days=1)
        return [CostItem(provider="aws", account_id=self.account_id(), usage_date=d, service="Amazon Simple Storage Service", resource_type="storage",
                         environment=self.environment, region="global", cost_usd=self.cost, cost_original=self.cost)]

    def fetch_resources(self):
        return [ResourceItem(provider="aws", account_id=self.account_id(), resource_id=f"i-{self.environment}", name=f"real-{self.environment}", resource_type="compute",
                             service="Amazon Elastic Compute Cloud - Compute", environment=self.environment, region="ap-south-1")]

    def fetch_metrics(self, resources, start, end, step_minutes=60):
        return []

    def test_connection(self):
        self.api_calls += 1
        if self.ok:
            return {"ok": True, "message": "Connected", "account": self.account_id(), "checks": [{"name": "Sign in", "ok": True, "detail": "ok"}]}
        return {"ok": False, "message": "Denied", "checks": [{"name": "Sign in", "ok": False, "detail": "Denied"}]}


@pytest.fixture
def fake_live(monkeypatch):
    """Route every live connector to FakeLive (no network)."""
    from app.api.routes import cloud_accounts as route
    from app import services

    holder = {"ok": True}
    build = lambda name, inr, config=None: FakeLive(config, ok=holder["ok"])  # noqa: E731
    monkeypatch.setattr(route, "build_live_provider", build)
    monkeypatch.setattr(services.providers, "build_live_provider", build)
    return holder


@pytest.fixture(autouse=True)
def restore_modes(seeded, monkeypatch):
    """Every test starts and ends with all clouds in mock mode and no live rows.

    The background load after a mode change is replaced here (it would race the in-memory test
    database); test_load_active_backfills_first_then_fills_the_gap covers what it runs.
    """
    from app.api.routes import cloud_accounts as route

    monkeypatch.setattr(route, "_load_in_background", lambda provider, environment=None: None)
    yield
    from app.core.database import SessionLocal
    from app.models import AppSetting

    db = SessionLocal()
    db.query(CloudAccount).delete()
    db.query(CloudConnection).delete()
    db.query(CostRecord).filter(CostRecord.source == "live").delete()
    db.query(Resource).filter(Resource.source == "live").delete()
    db.query(SyncRun).filter(SyncRun.data_source == "live").delete()
    db.query(AppSetting).filter(AppSetting.key == settings_service.WEBHOOKS_KEY).delete()
    db.commit()
    db.close()


def _test_and_save(client, h, activate=False, form=AWS_FORM, environment="production"):
    r = client.post(f"{API}/cloud-accounts/aws/test", json={"environment": environment, "config": form}, headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    r = client.put(f"{API}/cloud-accounts/aws/config", json={"environment": environment, "config": form, "activate": activate}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _yesterday(**kw):
    d = local_today() - timedelta(days=1)
    return Filters(d, d, **kw)


# ---------------------------------------------------------------- nothing about Live lives in the environment
def test_settings_have_no_live_configuration():
    from app.core.config import Settings

    banned = ("AWS_", "AZURE_", "GCP_", "GOOGLE_", "DATA_SOURCE", "ENV_TAG_KEY", "INSTALL_CLOUD_SDKS", "CREDENTIALS_ENCRYPTION_KEY")
    assert not [n for n in Settings.model_fields if n.startswith(banned)]


def test_every_cloud_starts_in_mock(client, viewer_headers):
    st = client.get(f"{API}/sync/status", headers=viewer_headers).json()
    assert st["data_source"] == "mock"
    assert [p["mode"] for p in st["providers"]] == ["mock", "mock", "mock"]
    assert all(p["connections"] == [] and p["account_id"] for p in st["providers"])


def test_connector_without_config_is_not_configured():
    assert AWSProvider().is_configured() is False


# ---------------------------------------------------------------- encryption
def test_encrypt_roundtrip_and_wrong_key(monkeypatch):
    from app.core import crypto

    token = encrypt_secrets({"k": "secret-value"})
    assert "secret-value" not in token and decrypt_secrets(token) == {"k": "secret-value"}
    monkeypatch.setattr(crypto, "_material", lambda: b"another key")
    with pytest.raises(CredentialsUnreadable):
        decrypt_secrets(token)


def test_secret_is_encrypted_in_db_and_never_returned(client, admin_headers, db, fake_live):
    view = _test_and_save(client, admin_headers)
    assert "super-secret-value" not in str(view)
    assert view["secrets_set"]["secret_access_key"] is True and "secret_access_key" not in view["values"]
    db.expire_all()
    row = db.get(CloudConnection, ("aws", "production"))
    assert "super-secret-value" not in str(row.config) and "super-secret-value" not in row.secrets_encrypted
    assert decrypt_secrets(row.secrets_encrypted)["secret_access_key"] == "super-secret-value"
    assert "super-secret-value" not in client.get(f"{API}/cloud-accounts/aws", headers=admin_headers).text


def test_blank_secret_keeps_saved_one(client, admin_headers, db, fake_live):
    _test_and_save(client, admin_headers)
    _test_and_save(client, admin_headers, form={**AWS_FORM, "secret_access_key": "", "regions": "us-east-1"})
    db.expire_all()
    row = db.get(CloudConnection, ("aws", "production"))
    assert decrypt_secrets(row.secrets_encrypted)["secret_access_key"] == "super-secret-value"
    assert row.config["regions"] == "us-east-1"


def test_unreadable_secret_is_reported_not_fatal(client, admin_headers, fake_live, monkeypatch):
    from app.core import crypto

    _test_and_save(client, admin_headers)
    monkeypatch.setattr(crypto, "_material", lambda: b"rotated key")
    view = client.get(f"{API}/cloud-accounts/aws", headers=admin_headers).json()
    assert view["secrets_unreadable"] is True and view["secrets_set"]["secret_access_key"] is False


# ---------------------------------------------------------------- validation & rules
def test_config_endpoints_require_admin(client, viewer_headers):
    body = {"environment": "production", "config": {}}
    assert client.get(f"{API}/cloud-accounts/aws", headers=viewer_headers).status_code == 403
    assert client.post(f"{API}/cloud-accounts/aws/test", json=body, headers=viewer_headers).status_code == 403
    assert client.put(f"{API}/cloud-accounts/aws/mode", json={"mode": "live"}, headers=viewer_headers).status_code == 403
    assert client.delete(f"{API}/cloud-accounts/aws/config", headers=viewer_headers).status_code == 403


def test_unknown_provider_is_404(client, admin_headers):
    assert client.get(f"{API}/cloud-accounts/oracle", headers=admin_headers).status_code == 404


@pytest.mark.parametrize("environment", ["unassigned", "qa", ""])
def test_environment_must_be_from_the_list(client, admin_headers, environment):
    r = client.post(f"{API}/cloud-accounts/aws/test", json={"environment": environment, "config": AWS_FORM}, headers=admin_headers)
    assert r.status_code == 422
    assert client.get(f"{API}/cloud-accounts/aws", params={"environment": "unassigned"}, headers=admin_headers).status_code == 422


def test_missing_and_malformed_fields_are_rejected_before_any_cloud_call(client, admin_headers):
    form = {**AWS_FORM, "access_key_id": "bad key", "secret_access_key": ""}
    r = client.post(f"{API}/cloud-accounts/aws/test", json={"environment": "production", "config": form}, headers=admin_headers)
    assert r.status_code == 422
    assert {d["loc"][-1] for d in r.json()["detail"]} == {"access_key_id", "secret_access_key"}


def test_instance_role_needs_no_keys():
    assert cloud_accounts.validate("aws", {"auth_method": "default_chain", "regions": "ap-south-1", "cost_explorer_region": "us-east-1"}) == []


@pytest.mark.parametrize("table", ["p.d.t`; DROP TABLE x; --", "p.d", "p d.t.x", "p.d.t' OR '1"])
def test_gcp_table_name_cannot_inject_sql(table):
    cfg = {"service_account_json": '{"type":"service_account","private_key":"k","client_email":"e"}', "project_id": "p", "billing_export_table": table}
    assert [e["field"] for e in cloud_accounts.validate("gcp", cfg)] == ["billing_export_table"]


@pytest.mark.parametrize("key,msg", [("not json", "not valid JSON"), ('{"type":"user"}', "not a service account")])
def test_gcp_key_is_checked(key, msg):
    assert msg in cloud_accounts.validate("gcp", {"service_account_json": key, "project_id": "p", "billing_export_table": "p.d.t"})[0]["message"]


def test_azure_guid_format():
    cfg = {"tenant_id": "x", "client_id": "x", "client_secret": "s", "subscription_id": "x"}
    assert {e["field"] for e in cloud_accounts.validate("azure", cfg)} == {"tenant_id", "client_id", "subscription_id"}


def test_cannot_save_without_passing_test(client, admin_headers, fake_live):
    body = {"environment": "production", "config": AWS_FORM}
    assert client.put(f"{API}/cloud-accounts/aws/config", json=body, headers=admin_headers).status_code == 409
    fake_live["ok"] = False
    assert client.post(f"{API}/cloud-accounts/aws/test", json=body, headers=admin_headers).json()["ok"] is False
    assert client.put(f"{API}/cloud-accounts/aws/config", json=body, headers=admin_headers).status_code == 409


def test_cannot_save_values_other_than_the_tested_ones(client, admin_headers, fake_live):
    body = {"environment": "production", "config": AWS_FORM}
    assert client.post(f"{API}/cloud-accounts/aws/test", json=body, headers=admin_headers).json()["ok"]
    edited = {"environment": "production", "config": {**AWS_FORM, "secret_access_key": "different"}}
    assert client.put(f"{API}/cloud-accounts/aws/config", json=edited, headers=admin_headers).status_code == 409


def test_test_for_one_environment_does_not_validate_another(client, admin_headers, fake_live):
    assert client.post(f"{API}/cloud-accounts/aws/test", json={"environment": "production", "config": AWS_FORM}, headers=admin_headers).json()["ok"]
    assert client.put(f"{API}/cloud-accounts/aws/config", json={"environment": "staging", "config": AWS_FORM}, headers=admin_headers).status_code == 409


def test_cannot_switch_to_live_until_one_environment_is_validated(client, admin_headers, fake_live):
    assert client.put(f"{API}/cloud-accounts/aws/mode", json={"mode": "live"}, headers=admin_headers).status_code == 409
    _test_and_save(client, admin_headers)
    assert client.put(f"{API}/cloud-accounts/aws/mode", json={"mode": "live"}, headers=admin_headers).json()["mode"] == "live"


def test_failed_retest_withdraws_validation(client, admin_headers, fake_live):
    _test_and_save(client, admin_headers)
    assert client.get(f"{API}/cloud-accounts/aws", headers=admin_headers).json()["verified"] is True
    fake_live["ok"] = False
    client.post(f"{API}/cloud-accounts/aws/test", json={"environment": "production", "config": {**AWS_FORM, "secret_access_key": ""}}, headers=admin_headers)
    assert client.get(f"{API}/cloud-accounts/aws", headers=admin_headers).json()["verified"] is False
    assert client.put(f"{API}/cloud-accounts/aws/mode", json={"mode": "live"}, headers=admin_headers).status_code == 409


# ---------------------------------------------------------------- one account per environment
def test_same_account_is_refused_for_a_second_environment(client, admin_headers, db, fake_live):
    _test_and_save(client, admin_headers)
    body = {"environment": "staging", "config": AWS_FORM}
    r = client.post(f"{API}/cloud-accounts/aws/test", json=body, headers=admin_headers).json()
    assert r["ok"] is False and "already configured for Production" in r["message"]
    assert client.put(f"{API}/cloud-accounts/aws/config", json=body, headers=admin_headers).status_code == 409
    db.expire_all()
    assert [c.environment for c in cloud_accounts.saved_connections(db, "aws")] == ["production"]


def test_saving_is_refused_if_another_environment_took_the_account_after_the_test(client, admin_headers, fake_live):
    prod, stag = {"environment": "production", "config": AWS_FORM}, {"environment": "staging", "config": AWS_FORM}
    assert client.post(f"{API}/cloud-accounts/aws/test", json=prod, headers=admin_headers).json()["ok"]
    assert client.post(f"{API}/cloud-accounts/aws/test", json=stag, headers=admin_headers).json()["ok"]  # nothing saved yet
    assert client.put(f"{API}/cloud-accounts/aws/config", json=prod, headers=admin_headers).status_code == 200
    r = client.put(f"{API}/cloud-accounts/aws/config", json=stag, headers=admin_headers)
    assert r.status_code == 409 and "count twice" in r.json()["detail"]


def test_retesting_an_environments_own_account_is_allowed(client, admin_headers, fake_live):
    _test_and_save(client, admin_headers)
    _test_and_save(client, admin_headers, form={**AWS_FORM, "secret_access_key": ""})


def test_each_environment_shows_its_own_account_and_unconfigured_ones_show_nothing(db, client, admin_headers, viewer_headers, fake_live):
    """AWS Live with Production and Staging connected: Development has no data, and no mock data leaks in."""
    mock_dev = analytics.total_cost(db, _yesterday(providers=["aws"], environments=["development"]))
    assert mock_dev > 0
    azure_before = analytics.total_cost(db, _yesterday(providers=["azure"]))

    _test_and_save(client, admin_headers, activate=True)
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    db.expire_all()
    assert {r.environment: r.status for r in run_job(db, "manual", providers=["aws"], triggered_by="test")} == {"production": "success", "staging": "success"}

    for env, expected in (("production", 7.0), ("staging", 7.0), ("development", 0.0)):
        assert analytics.total_cost(db, _yesterday(providers=["aws"], environments=[env])) == pytest.approx(expected)
    assert analytics.total_cost(db, _yesterday(providers=["aws"])) == pytest.approx(14.0)
    assert analytics.total_cost(db, _yesterday(providers=["azure"])) == pytest.approx(azure_before)

    day = (local_today() - timedelta(days=1)).isoformat()
    for path in ("/dashboard/summary", "/reports/summary"):
        r = client.get(f"{API}{path}", params={"provider": "aws", "environment": "staging", "start": day, "end": day}, headers=viewer_headers).json()
        assert (r.get("period_total") if path.startswith("/dash") else r["total"]) == pytest.approx(7.0)
    r = client.get(f"{API}/costs/breakdown", params={"provider": "aws", "dimension": "environment", "start": day, "end": day}, headers=viewer_headers).json()
    assert {x["key"] for x in r["rows"]} == {"production", "staging"}
    names = {x["name"] for x in client.get(f"{API}/resources", params={"provider": "aws", "environment": "staging"}, headers=viewer_headers).json()}
    assert names == {"real-staging"}
    assert client.get(f"{API}/resources", params={"provider": "aws", "environment": "development"}, headers=viewer_headers).json() == []

    st = client.get(f"{API}/sync/status", headers=viewer_headers).json()
    aws = st["providers"][0]
    assert st["data_source"] == "mixed" and aws["mode"] == "live"
    assert [(c["environment"], c["account"]) for c in aws["connections"]] == [("production", "111111111111"), ("staging", "222222222222")]
    assert aws["account_id"] == "111111111111, 222222222222"


def test_one_failing_connection_does_not_stop_the_other_and_is_reported(db, client, admin_headers, viewer_headers, fake_live, monkeypatch):
    _test_and_save(client, admin_headers, activate=True)
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    db.expire_all()
    real = FakeLive.fetch_costs

    def flaky(self, start, end):
        if self.environment == "production":
            raise RuntimeError("credentials expired")
        return real(self, start, end)

    monkeypatch.setattr(FakeLive, "fetch_costs", flaky)
    runs = {r.environment: r.status for r in run_job(db, "manual", providers=["aws"], triggered_by="test")}
    assert runs == {"production": "failed", "staging": "success"}
    assert analytics.total_cost(db, _yesterday(providers=["aws"], environments=["staging"])) == pytest.approx(7.0)
    aws = client.get(f"{API}/sync/status", headers=viewer_headers).json()["providers"][0]
    assert aws["last_run"]["status"] == "failed" and "credentials expired" in aws["last_run"]["error"]


def test_removing_a_connection_hides_its_data_and_the_last_one_returns_to_mock(db, client, admin_headers, viewer_headers, fake_live):
    _test_and_save(client, admin_headers, activate=True)
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    db.expire_all()
    run_job(db, "manual", providers=["aws"], triggered_by="test")

    view = client.delete(f"{API}/cloud-accounts/aws/config", params={"environment": "staging"}, headers=admin_headers).json()
    assert view["mode"] == "live" and view["has_saved_config"] is False
    db.expire_all()
    assert analytics.total_cost(db, _yesterday(providers=["aws"], environments=["staging"])) == 0
    assert analytics.total_cost(db, _yesterday(providers=["aws"], environments=["production"])) == pytest.approx(7.0)

    view = client.delete(f"{API}/cloud-accounts/aws/config", params={"environment": "production"}, headers=admin_headers).json()
    assert view["mode"] == "mock"
    db.expire_all()
    assert db.get(CloudConnection, ("aws", "production")) is None
    assert analytics.total_cost(db, _yesterday(providers=["aws"])) > 100


def test_replacing_an_environments_account_hides_the_old_accounts_figures(db, client, admin_headers, fake_live):
    _test_and_save(client, admin_headers, activate=True)
    db.expire_all()
    run_job(db, "manual", providers=["aws"], triggered_by="test")
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="production")  # new account, same environment
    db.expire_all()
    run_job(db, "manual", providers=["aws"], triggered_by="test")
    assert analytics.total_cost(db, _yesterday(providers=["aws"], environments=["production"])) == pytest.approx(7.0)


# ---------------------------------------------------------------- data follows the selected mode
def test_switching_mode_keeps_both_data_sets(db, client, admin_headers, viewer_headers, fake_live):
    mock_aws = analytics.total_cost(db, _yesterday(providers=["aws"]))
    assert mock_aws > 0
    _test_and_save(client, admin_headers, activate=True)
    db.expire_all()
    live = FakeLive({"environment": "production", "access_key_id": AWS_FORM["access_key_id"]})
    upsert_costs(db, live.fetch_costs(None, None), "live")
    upsert_resources(db, live.fetch_resources(), "live")
    assert analytics.total_cost(db, _yesterday(providers=["aws"])) == pytest.approx(7.0)
    accounts = client.get(f"{API}/costs/filters", headers=viewer_headers).json()["accounts"]
    assert "111111111111" in accounts and "123456789012" not in accounts
    assert client.get("/health").json()["data_source"] == "mixed"

    assert client.put(f"{API}/cloud-accounts/aws/mode", json={"mode": "mock"}, headers=admin_headers).status_code == 200
    db.expire_all()
    assert analytics.total_cost(db, _yesterday(providers=["aws"])) == pytest.approx(mock_aws)
    assert db.query(CostRecord).filter(CostRecord.source == "live").count() >= 1


def test_mock_resource_detail_hidden_when_cloud_is_live(db, client, admin_headers, viewer_headers, fake_live):
    pk = db.query(Resource).filter(Resource.provider == "aws", Resource.source == "mock").first().id
    assert client.get(f"{API}/resources/{pk}", headers=viewer_headers).status_code == 200
    _test_and_save(client, admin_headers, activate=True)
    assert client.get(f"{API}/resources/{pk}", headers=viewer_headers).status_code == 404


def test_scheduler_sync_uses_each_clouds_mode(db, client, admin_headers, fake_live):
    _test_and_save(client, admin_headers, activate=True)
    db.expire_all()
    runs = run_job(db, "manual", triggered_by="test")
    assert {r.provider: r.data_source for r in runs} == {"aws": "live", "azure": "mock", "gcp": "mock"}
    assert db.query(CostRecord).filter(CostRecord.provider == "azure", CostRecord.source == "live").count() == 0
    assert db.query(Resource).filter(Resource.resource_id == "i-production").one().source == "live"


def test_live_intraday_refresh_is_rate_limited_per_connection(db, client, admin_headers, fake_live):
    """A 15-minute intraday job must not bill Cost Explorer every 15 minutes."""
    _test_and_save(client, admin_headers, activate=True)
    db.expire_all()
    first = run_job(db, "intraday", triggered_by="test", providers=["aws"])
    assert len(first) == 1
    assert run_job(db, "intraday", triggered_by="test", providers=["aws"]) == []
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    db.expire_all()
    assert [r.environment for r in run_job(db, "intraday", triggered_by="test", providers=["aws"])] == ["staging"]
    first[0].started_at = datetime.now(timezone.utc) - timedelta(minutes=361)
    db.commit()
    assert [r.environment for r in run_job(db, "intraday", triggered_by="test", providers=["aws"])] == ["production"]


def test_load_active_backfills_first_then_fills_the_gap(db, client, admin_headers, fake_live):
    _test_and_save(client, admin_headers, activate=True)
    db.expire_all()
    first = load_active(db, "aws")[0]
    assert first.job == "backfill" and first.data_source == "live" and first.status == "success"
    assert load_active(db, "aws")[0].job == "manual"

    # a newly added environment gets its own first load and leaves the others alone
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    db.expire_all()
    runs = load_active(db, "aws", environment="staging")
    assert [(r.environment, r.job) for r in runs] == [("staging", "backfill")]

    # back on mock after a gap: the missing mock days are fetched, so the trend has no hole
    cloud_accounts.set_mode(db, "aws", "mock")
    gap_start = local_today() - timedelta(days=9)
    db.query(CostRecord).filter(CostRecord.provider == "aws", CostRecord.source == "mock", CostRecord.usage_date > gap_start).delete()
    db.commit()
    assert load_active(db, "aws")[0].status == "success"
    days = {d for (d,) in db.query(CostRecord.usage_date).filter(CostRecord.provider == "aws", CostRecord.source == "mock", CostRecord.usage_date >= gap_start)}
    assert len(days) == 10


def test_card_test_covers_every_connection(client, admin_headers, fake_live, monkeypatch):
    _test_and_save(client, admin_headers, activate=True)
    _test_and_save(client, admin_headers, form=STAGING_FORM, environment="staging")
    r = client.post(f"{API}/sync/test/aws", headers=admin_headers).json()
    assert r["ok"] is True and [c["name"] for c in r["checks"]] == ["Production: Sign in", "Staging: Sign in"]
    assert r["account"] == "111111111111, 222222222222"
    monkeypatch.setattr(FakeLive, "test_connection", lambda self: {"ok": False, "message": "Denied", "checks": []})
    r = client.post(f"{API}/sync/test/aws", headers=admin_headers).json()
    assert r["ok"] is False and r["message"] == "Production: Denied; Staging: Denied"


def test_spike_demo_refused_for_live_cloud(client, admin_headers, fake_live):
    _test_and_save(client, admin_headers, activate=True)
    assert client.post(f"{API}/sync/mock/anomaly", json={"provider": "aws", "factor": 2, "days_ago": 1}, headers=admin_headers).status_code == 400
    assert client.post(f"{API}/sync/mock/anomaly", json={"provider": "azure", "factor": 2, "days_ago": 1}, headers=admin_headers).status_code == 200
    assert client.delete(f"{API}/sync/mock/anomaly", headers=admin_headers).json()["cleared"] == 1


# ---------------------------------------------------------------- upgrades
def test_existing_database_is_upgraded(tmp_path):
    """Upgrading a database from before Resource.source, SyncRun.environment and per-environment connections."""
    from app.core.database import add_missing_columns

    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE resources (id INTEGER PRIMARY KEY, provider VARCHAR(10))"))
        conn.execute(text("CREATE TABLE sync_runs (id INTEGER PRIMARY KEY, provider VARCHAR(10))"))
        conn.execute(text("CREATE TABLE cloud_accounts (provider VARCHAR(10) PRIMARY KEY, mode VARCHAR(10), config TEXT NOT NULL, secrets_encrypted TEXT, updated_at TEXT)"))
        conn.execute(text("INSERT INTO resources (provider) VALUES ('aws')"))
        conn.execute(text("INSERT INTO cloud_accounts VALUES ('aws', 'mock', '{}', '', 'x')"))
    add_missing_columns(engine)
    add_missing_columns(engine)  # safe to run on every start
    assert {c["name"] for c in inspect(engine).get_columns("cloud_accounts")} == {"provider", "mode", "updated_at"}
    assert "environment" in {c["name"] for c in inspect(engine).get_columns("sync_runs")}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT source FROM resources")).scalar() == "mock"
        assert conn.execute(text("SELECT mode FROM cloud_accounts")).scalar() == "mock"


# ---------------------------------------------------------------- webhooks on the Settings screen
def test_webhooks_default_to_the_test_inbox(db):
    urls = settings_service.webhook_urls(db)
    assert "mock-receiver" in urls["slack"] and "mock-receiver" in urls["teams"]


def test_webhooks_are_saved_encrypted_and_never_returned(client, admin_headers, viewer_headers, db):
    url = "https://hooks.slack.com/services/T000/B000/secretpart"
    r = client.put(f"{API}/settings", json={"slack_webhook_url": url}, headers=admin_headers)
    assert r.status_code == 200 and "secretpart" not in r.text
    assert r.json()["system"]["webhooks"] == {"slack_saved": True, "teams_saved": False, "unreadable": False}
    assert "secretpart" not in client.get(f"{API}/settings", headers=viewer_headers).text
    db.expire_all()
    assert "secretpart" not in str(settings_service.get_value(db, settings_service.WEBHOOKS_KEY))
    urls = settings_service.webhook_urls(db)
    assert urls["slack"] == url and "mock-receiver" in urls["teams"]


def test_saving_other_settings_keeps_webhooks_and_blank_returns_to_test_inbox(client, admin_headers, db):
    url = "https://outlook.office.com/webhook/secretpart"
    client.put(f"{API}/settings", json={"teams_webhook_url": url}, headers=admin_headers)
    client.put(f"{API}/settings", json={"idle_cpu_threshold": 11}, headers=admin_headers)
    db.expire_all()
    assert settings_service.webhook_urls(db)["teams"] == url
    client.put(f"{API}/settings", json={"teams_webhook_url": "", "idle_cpu_threshold": 10}, headers=admin_headers)
    db.expire_all()
    assert "mock-receiver" in settings_service.webhook_urls(db)["teams"]


def test_webhook_must_be_https_and_admin_only(client, admin_headers, viewer_headers):
    for bad in ("http://169.254.169.254/latest", "ftp://x", "hooks.slack.com/x"):
        assert client.put(f"{API}/settings", json={"slack_webhook_url": bad}, headers=admin_headers).status_code == 422
    assert client.put(f"{API}/settings", json={"slack_webhook_url": "https://x.example"}, headers=viewer_headers).status_code == 403


def test_unreadable_webhooks_fail_visibly_not_to_the_test_inbox(client, admin_headers, db, monkeypatch):
    from app.core import crypto

    client.put(f"{API}/settings", json={"slack_webhook_url": "https://hooks.slack.com/x"}, headers=admin_headers)
    db.expire_all()
    monkeypatch.setattr(crypto, "_material", lambda: b"rotated key")
    assert settings_service.webhook_urls(db) == {"slack": "", "teams": ""}
    assert settings_service.webhook_status(db)["unreadable"] is True


def test_alertmanager_file_follows_the_saved_url(client, admin_headers, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ALERTMANAGER_SHARED_DIR", str(tmp_path))
    client.put(f"{API}/settings", json={"slack_webhook_url": "https://hooks.slack.com/one"}, headers=admin_headers)
    assert (tmp_path / "slack_webhook_url").read_text() == "https://hooks.slack.com/one"
    client.put(f"{API}/settings", json={"slack_webhook_url": ""}, headers=admin_headers)
    assert "mock-receiver" in (tmp_path / "slack_webhook_url").read_text()


# ---------------------------------------------------------------- connectors with form values
def test_cost_explorer_period_clamps():
    today = date(2026, 10, 31)
    # IST "tomorrow + 1" on the last day of the month would be rejected
    assert cost_explorer_period(date(2026, 11, 1), date(2026, 11, 2), today) is None
    assert cost_explorer_period(date(2026, 10, 28), date(2026, 11, 2), today) == (date(2026, 10, 28), date(2026, 11, 1))
    start, _ = cost_explorer_period(date(2020, 1, 1), date(2026, 10, 31), today)
    assert start == date(2025, 9, 1)


def _stubbed_aws(responses, environment="production"):
    """AWSProvider whose clients answer from {service: {method: result or exception}}."""
    p = AWSProvider(config={**AWS_FORM, "environment": environment})
    calls = []

    class Client:
        def __init__(self, svc):
            self.svc = svc

        def __getattr__(self, method):
            def call(**kw):
                calls.append((self.svc, method, kw))
                result = responses.get(self.svc, {}).get(method, {})
                if isinstance(result, Exception):
                    raise result
                return result
            return call

    class Session:
        def client(self, svc, **kw):
            return Client(svc)

    p._session = Session()
    p.calls = calls
    return p


def _client_error(code, message):
    from botocore.exceptions import ClientError

    return ClientError({"Error": {"Code": code, "Message": message}}, "Op")


def test_aws_costs_belong_to_the_chosen_environment_and_only_this_account():
    day = local_today() - timedelta(days=2)
    p = _stubbed_aws({
        "sts": {"get_caller_identity": {"Account": "111122223333"}},
        "ce": {"get_cost_and_usage": {"ResultsByTime": [{"TimePeriod": {"Start": day.isoformat(), "End": day.isoformat()}, "Groups": [
            {"Keys": ["Amazon Simple Storage Service"], "Metrics": {"UnblendedCost": {"Amount": "5", "Unit": "USD"}}},
        ]}]}},
    }, environment="staging")
    items = p.fetch_costs(day, day + timedelta(days=1))
    assert [(i.environment, i.account_id, i.cost_usd) for i in items] == [("staging", "111122223333", 5.0)]
    kw = next(c[2] for c in p.calls if c[1] == "get_cost_and_usage")
    assert kw["Filter"] == {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["111122223333"]}}
    assert kw["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]  # tags no longer decide the environment


def test_aws_resources_use_the_environment_not_tags_and_rds_ids_are_unique():
    arn = "arn:aws:rds:ap-south-1:111122223333:db:orders"

    class Pager:
        def __init__(self, pages):
            self.pages = pages

        def paginate(self):
            return self.pages

    p = _stubbed_aws({"sts": {"get_caller_identity": {"Account": "111122223333"}}}, environment="staging")
    real_client = p._session.client

    def client(svc, **kw):
        c = real_client(svc, **kw)
        pages = {
            "ec2": [{"Reservations": [{"Instances": [{"InstanceId": "i-1", "Tags": [{"Key": "environment", "Value": "production"}], "State": {"Name": "running"}}]}]}],
            "rds": [{"DBInstances": [{"DBInstanceIdentifier": "orders", "DBInstanceArn": arn, "DBInstanceStatus": "available"}]}],
        }.get(svc)
        if pages is not None:
            object.__setattr__(c, "get_paginator", lambda name: Pager(pages))
        return c

    p._session.client = client
    res = p.fetch_resources()
    assert {r.environment for r in res} == {"staging"}
    assert next(r for r in res if r.resource_type == "database").resource_id == arn


def test_aws_test_reports_every_check():
    p = _stubbed_aws({"sts": {"get_caller_identity": {"Account": "111122223333"}}})
    r = p.test_connection()
    assert r["ok"] is True and r["account"] == "111122223333"
    assert [c["name"] for c in r["checks"]] == ["Sign in (STS)", "Cost Explorer", "EC2 inventory", "RDS inventory", "CloudWatch metrics"]


def test_aws_sign_in_works_without_a_default_region(monkeypatch):
    """Containers set no AWS_DEFAULT_REGION, so every client needs an explicit region."""
    import boto3

    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/nonexistent")
    session = boto3.Session(aws_access_key_id="x", aws_secret_access_key="y")
    real_client, seen = session.client, []

    def client(name, **kw):
        seen.append((name, kw.get("region_name")))
        c = real_client(name, **kw)
        c.get_caller_identity = lambda: {"Account": "111122223333"}
        return c

    session.client = client
    p = AWSProvider(config={**AWS_FORM})
    p._session = session
    assert p.account_id() == "111122223333"
    assert seen == [("sts", "us-east-1")]


def test_aws_bad_keys_stop_at_sign_in_with_a_hint():
    p = _stubbed_aws({"sts": {"get_caller_identity": _client_error("InvalidClientTokenId", "The security token is invalid")}})
    r = p.test_connection()
    assert r["ok"] is False and len(r["checks"]) == 1
    assert "rejected these credentials" in r["checks"][0]["detail"]


def test_aws_missing_permissions_are_all_listed():
    p = _stubbed_aws({
        "sts": {"get_caller_identity": {"Account": "111122223333"}},
        "ce": {"get_cost_and_usage": _client_error("AccessDeniedException", "User not enabled for cost explorer access")},
        "rds": {"describe_db_instances": _client_error("AccessDenied", "not authorized")},
    })
    r = p.test_connection()
    by_name = {c["name"]: c for c in r["checks"]}
    assert r["ok"] is False and "account" not in r
    assert "Enable it in the AWS Billing console" in by_name["Cost Explorer"]["detail"]
    assert "iam-policy.json" in by_name["RDS inventory"]["detail"]
    assert by_name["EC2 inventory"]["ok"] is True


def test_secrets_are_scrubbed_from_error_messages():
    p = _stubbed_aws({"sts": {"get_caller_identity": ValueError("bad super-secret-value here")}})
    assert "super-secret-value" not in p.test_connection()["message"]


def test_aws_session_uses_form_values(monkeypatch):
    import boto3

    captured = {}
    monkeypatch.setattr(boto3, "Session", lambda **kw: captured.update(kw) or object())
    AWSProvider(config={**AWS_FORM, "session_token": "tok"}).session()
    assert captured == {"aws_access_key_id": "AKIAABCDEFGHIJKLMNOP", "aws_secret_access_key": "super-secret-value", "aws_session_token": "tok"}
    captured.clear()
    AWSProvider(config={**AWS_FORM, "auth_method": "default_chain"}).session()
    assert captured == {}


def test_azure_uses_form_values():
    from app.services.providers.azure import AzureProvider

    cfg = {"tenant_id": "t", "client_id": "c", "client_secret": "s", "subscription_id": "sub", "environment": "staging"}
    p = AzureProvider(config=cfg)
    assert p.is_configured() and p.account_id() == "sub" and p.scope == "/subscriptions/sub" and p.environment == "staging"
    assert AzureProvider(config={**cfg, "client_secret": ""}).is_configured() is False


def test_azure_rejected_login_gets_a_plain_hint():
    """The hint must hold for every sign-in failure, including a tenant that does not exist."""
    from azure.core.exceptions import ClientAuthenticationError

    from app.services.providers.azure import AzureProvider

    class Credential:
        def get_token(self, scope):
            raise ClientAuthenticationError("Unable to get authority configuration for https://login.microsoftonline.com/x")

    p = AzureProvider(config={"tenant_id": "t", "client_id": "c", "client_secret": "sec", "subscription_id": "sub"})
    p._cred = Credential()
    r = p.test_connection()
    assert r["ok"] is False and len(r["checks"]) == 1
    assert "Check the tenant ID, client ID and client secret" in r["checks"][0]["detail"]


def test_gcp_needs_a_pasted_key_and_reads_only_its_project():
    from app.services.providers.gcp import BILLING_SQL, GCPProvider

    base = {"project_id": "p", "billing_export_table": "p.d.t", "environment": "staging"}
    assert GCPProvider(config={**base, "service_account_json": "{}"}).is_configured() is True
    assert GCPProvider(config=base).is_configured() is False
    # one billing export can cover many projects, and each project may be another environment's connection
    assert "project.id = @project" in BILLING_SQL
