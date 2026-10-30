from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.models import CostRecord, Resource, ResourceMetric, SyncRun
from app.services import analytics
from app.services.analytics import Filters
from app.services.ingestion import local_today, run_job, sync_provider, upsert_costs
from app.services.providers.base import CostItem


def _f(days=30, **kw):
    end = local_today()
    return Filters(end - timedelta(days=days - 1), end, **kw)


def test_backfill_loaded_all_providers(db):
    provs = {p for (p,) in db.execute(select(CostRecord.provider).distinct()).all()}
    assert provs == {"aws", "azure", "gcp"}
    assert db.scalar(select(func.count()).select_from(Resource)) == 25
    assert db.scalar(select(func.count()).select_from(ResourceMetric)) > 1000
    runs = db.execute(select(SyncRun).where(SyncRun.job == "backfill")).scalars().all()
    assert {r.status for r in runs} == {"success"}


def test_resync_is_idempotent(db):
    before_rows = db.scalar(select(func.count()).select_from(CostRecord))
    before_sum = analytics.total_cost(db, _f(7))
    run_job(db, "daily", triggered_by="test")
    assert db.scalar(select(func.count()).select_from(CostRecord)) == before_rows
    assert analytics.total_cost(db, _f(7)) == pytest.approx(before_sum, rel=0.02)  # only today's partial may move


def test_upsert_merges_duplicate_keys(db):
    day = local_today() - timedelta(days=400)
    item = dict(provider="aws", account_id="t", usage_date=day, service="Test", resource_type="other", environment="production", region="global", cost_usd=1.0, cost_original=1.0)
    n = upsert_costs(db, [CostItem(**item), CostItem(**item)], "mock")
    assert n == 1
    row = db.execute(select(CostRecord).where(CostRecord.account_id == "t")).scalar_one()
    assert float(row.cost_usd) == pytest.approx(2.0)
    db.delete(row)
    db.commit()


def test_unconfigured_provider_is_skipped(db):
    from app.services.providers.aws import AWSProvider

    run = sync_provider(db, "aws", AWSProvider(), job="manual", cost_start=local_today(), cost_end=local_today() + timedelta(days=1), triggered_by="test")
    assert run.status == "skipped" and "not configured" in run.error


def test_breakdowns_add_up_to_total(db):
    f = _f(30)
    total = analytics.total_cost(db, f)
    for dim in ("provider", "environment", "resource_type", "service"):
        assert sum(r["cost"] for r in analytics.breakdown(db, f, dim, limit=500)) == pytest.approx(total, rel=1e-6)


def test_daily_series_zero_filled_and_matches_total(db):
    f = _f(14)
    s = analytics.daily_series(db, f, "provider")
    assert len(s["points"]) == 14
    assert sum(p["total"] for p in s["points"]) == pytest.approx(analytics.total_cost(db, f), rel=1e-4)
    for p in s["points"]:
        assert p["total"] == pytest.approx(sum(p[k] for k in s["keys"]), abs=0.05)


def test_filters_reduce_totals(db):
    all_cost = analytics.total_cost(db, _f(30))
    aws = analytics.total_cost(db, _f(30, providers=["aws"]))
    prod_aws = analytics.total_cost(db, _f(30, providers=["aws"], environments=["production"]))
    assert 0 < prod_aws < aws < all_cost


def test_summary_and_budget(db):
    s = analytics.summary(db, _f(30))
    assert s["period_total"] > 0
    assert s["month"]["forecast"] >= s["month"]["mtd"] * 0.9
    assert s["budget"]["budget"] == 120000
    assert s["budget"]["applies_to_filtered_view"] is True
    scoped = analytics.summary(db, _f(30, environments=["production"]))
    assert scoped["budget"]["applies_to_filtered_view"] is False


def test_monthly_trend_has_mom(db):
    m = analytics.monthly(db, _f(30), months=2)
    assert len(m["months"]) == 2
    assert m["months"][-1]["partial"] is True
    assert set(m["keys"]) == {"aws", "azure", "gcp"}


def test_anomalies_detect_injected_spike(db):
    from app.services import settings_service
    from app.services.providers import get_provider

    day = local_today() - timedelta(days=2)
    settings_service.set_value(db, "mock_anomalies", [{"provider": "gcp", "date": day.isoformat(), "factor": 4}])
    sync_provider(db, "gcp", get_provider("gcp", db), job="manual", cost_start=day, cost_end=day + timedelta(days=1), triggered_by="test")
    found = [a for a in analytics.anomalies(db, _f(10)) if a["provider"] == "gcp" and a["date"] == day.isoformat()]
    assert found and found[0]["change_pct"] > 40
    # clean up so other tests see normal data
    settings_service.set_value(db, "mock_anomalies", [])
    sync_provider(db, "gcp", get_provider("gcp", db), job="manual", cost_start=day, cost_end=day + timedelta(days=1), triggered_by="test")


def test_resources_status_and_recommendations(db):
    rows = analytics.resources(db, _f(30), limit=100)
    by_name = {r["name"]: r for r in rows}
    assert by_name["dev-jenkins-ec2"]["status"] == "idle"
    assert by_name["prod-nat-gateway"]["status"] == "no_metrics"
    recs = analytics.recommendations(db, _f(30))
    names = {r["resource"]: r for r in recs}
    assert names["ml-training-a100-vm"]["action"] == "stop_idle"
    assert names["s3-log-archive"]["action"] == "storage_tier"
    assert all(0 < r["monthly_savings"] < r["monthly_cost"] for r in recs)


def test_utilization_summary(db):
    u = analytics.utilization(db, _f(7), hours=48)
    assert {p["provider"] for p in u["providers"]} == {"aws", "azure", "gcp"}
    assert u["trend"] and u["counts"]["total"] == 25


def test_resource_detail(db):
    pk = db.execute(select(Resource.id).where(Resource.name == "prod-eks-cluster-01")).scalar_one()
    d = analytics.resource_detail(db, pk, 30)
    assert d["resource"]["name"] == "prod-eks-cluster-01"
    assert len(d["cost_series"]) == 30 and d["metrics"]
    assert analytics.resource_detail(db, 999999) is None
