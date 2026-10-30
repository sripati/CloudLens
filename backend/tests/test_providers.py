from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.providers.aws import parse_cost_explorer
from app.services.providers.azure import _merge_duplicates, parse_cost_query
from app.services.providers.gcp import parse_billing_rows
from app.services.providers.mock import ANOMALY_CYCLES, CATALOG, MockProvider

NOW = datetime(2026, 10, 15, 6, 30, tzinfo=timezone.utc)  # 12:00 IST


def test_mock_is_deterministic():
    a = MockProvider("aws", now=NOW).fetch_costs(date(2026, 10, 1), date(2026, 10, 8))
    b = MockProvider("aws", now=NOW).fetch_costs(date(2026, 10, 1), date(2026, 10, 8))
    assert [x.cost_usd for x in a] == [x.cost_usd for x in b]
    assert len(a) == 7 * len(CATALOG["aws"])


def test_mock_today_is_partial_and_future_is_empty():
    p = MockProvider("azure", now=NOW)
    today = p.fetch_costs(date(2026, 10, 15), date(2026, 10, 16))
    yesterday = p.fetch_costs(date(2026, 10, 14), date(2026, 10, 15))
    assert sum(i.cost_usd for i in today) < sum(i.cost_usd for i in yesterday) * 0.7
    assert p.fetch_costs(date(2026, 10, 20), date(2026, 10, 22)) == []


def test_mock_builtin_anomaly_spikes():
    prov, name, cycle, offset, mult = ANOMALY_CYCLES[0]
    d = date(2026, 10, 1)
    while d.toordinal() % cycle != offset:
        d += timedelta(days=1)
    p = MockProvider(prov, now=NOW + timedelta(days=60))
    spike = [i for i in p.fetch_costs(d, d + timedelta(days=1)) if name in i.resource_id][0].cost_usd
    normal = [i for i in p.fetch_costs(d - timedelta(days=1), d) if name in i.resource_id][0].cost_usd
    assert spike > normal * (mult * 0.7)


def test_mock_override_anomaly():
    d = date(2026, 10, 10)
    base = sum(i.cost_usd for i in MockProvider("gcp", now=NOW).fetch_costs(d, d + timedelta(days=1)))
    hit = sum(i.cost_usd for i in MockProvider("gcp", overrides=[{"provider": "gcp", "date": d.isoformat(), "factor": 3}], now=NOW).fetch_costs(d, d + timedelta(days=1)))
    assert hit > base * 2


def test_mock_metrics_within_bounds():
    p = MockProvider("aws", now=NOW)
    res = p.fetch_resources()
    samples = p.fetch_metrics(res, NOW - timedelta(hours=6), NOW, step_minutes=60)
    assert samples
    for s in samples:
        if s.cpu_percent is not None:
            assert 0 < s.cpu_percent < 100


def test_parse_aws_cost_explorer():
    pages = [{
        "ResultsByTime": [{
            "TimePeriod": {"Start": "2026-10-01", "End": "2026-10-02"},
            "Groups": [
                {"Keys": ["Amazon Elastic Compute Cloud - Compute", "environment$prod"],
                 "Metrics": {"UnblendedCost": {"Amount": "123.456", "Unit": "USD"}, "UsageQuantity": {"Amount": "48", "Unit": "Hrs"}}},
                {"Keys": ["Amazon Simple Storage Service", "environment$"],
                 "Metrics": {"UnblendedCost": {"Amount": "10", "Unit": "USD"}, "UsageQuantity": {"Amount": "1", "Unit": "GB-Mo"}}},
                {"Keys": ["Tax", "environment$"], "Metrics": {"UnblendedCost": {"Amount": "0", "Unit": "USD"}}},
            ],
        }]
    }]
    items = parse_cost_explorer(pages, "111122223333", 84.2)
    assert len(items) == 2  # zero-cost line skipped
    ec2 = items[0]
    assert ec2.usage_date == date(2026, 10, 1)
    assert ec2.resource_type == "compute" and ec2.environment == "production"
    assert ec2.cost_usd == pytest.approx(123.456)
    assert items[1].environment == "unassigned" and items[1].resource_type == "storage"


def test_parse_azure_cost_query_converts_inr():
    result = {
        "columns": [{"name": "Cost"}, {"name": "UsageDate"}, {"name": "ServiceName"}, {"name": "ResourceLocation"}, {"name": "TagKey"}, {"name": "TagValue"}, {"name": "Currency"}],
        "rows": [
            [8420.0, 20261001, "Virtual Machines", "CentralIndia", "environment", "prod", "INR"],
            [842.0, 20261001, "Virtual Machines", "CentralIndia", "environment", "prod", "INR"],
            [50.0, 20261002, "Storage", "SouthIndia", None, None, "USD"],
        ],
    }
    items = _merge_duplicates(parse_cost_query(result, "sub-1", 84.2))
    vm = [i for i in items if i.service == "Virtual Machines"][0]
    assert vm.cost_usd == pytest.approx(110.0)  # (8420 + 842) / 84.2
    assert vm.currency_original == "INR" and vm.region == "centralindia"
    st = [i for i in items if i.service == "Storage"][0]
    assert st.environment == "unassigned" and st.usage_date == date(2026, 10, 2)


def test_parse_gcp_billing_rows():
    rows = [
        {"usage_date": date(2026, 10, 1), "project_id": "p1", "service": "Compute Engine", "region": "asia-south1", "env": "dev",
         "currency": "USD", "conversion_rate": 1.0, "net_cost": 42.5, "usage_qty": 24, "usage_unit": "hour"},
        {"usage_date": "2026-10-01", "project_id": "p1", "service": "BigQuery", "region": None, "env": None,
         "currency": "INR", "conversion_rate": 83.0, "net_cost": 830.0, "usage_qty": 1, "usage_unit": "tebibyte"},
        {"usage_date": "2026-10-01", "project_id": "p1", "service": "Cloud Storage", "region": "us", "env": "prod",
         "currency": "USD", "conversion_rate": 1, "net_cost": 0.0},
    ]
    items = parse_billing_rows(rows, 84.2, "default")
    assert len(items) == 2
    assert items[0].environment == "development" and items[0].resource_type == "compute"
    assert items[1].cost_usd == pytest.approx(10.0) and items[1].region == "global"


def test_live_providers_report_not_configured(monkeypatch):
    from app.services.providers.aws import AWSProvider
    from app.services.providers.azure import AzureProvider
    from app.services.providers.gcp import GCPProvider

    for cls in (AWSProvider, AzureProvider, GCPProvider):
        p = cls()
        assert p.is_configured() is False
        assert p.test_connection()["ok"] is False


def test_aws_fetch_costs_paginates_with_stubber():
    """Exercise AWSProvider.fetch_costs against a stubbed Cost Explorer client (no network)."""
    import boto3
    from botocore.stub import Stubber

    from app.services.providers.aws import AWSProvider

    session = boto3.Session(aws_access_key_id="x", aws_secret_access_key="y", region_name="us-east-1")
    ce = session.client("ce", region_name="us-east-1")
    stub = Stubber(ce)
    page = lambda amount, token=None: {  # noqa: E731
        "ResultsByTime": [{"TimePeriod": {"Start": "2026-10-01", "End": "2026-10-02"}, "Estimated": False, "Total": {},
                           "Groups": [{"Keys": ["Amazon Simple Storage Service", "environment$dev"],
                                       "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}, "UsageQuantity": {"Amount": "1", "Unit": "GB"}}}]}],
        **({"NextPageToken": token} if token else {}),
    }
    stub.add_response("get_cost_and_usage", page("5.0", "t1"))
    stub.add_response("get_cost_and_usage", page("7.0"), expected_params=None)
    stub.activate()

    p = AWSProvider()
    p.is_configured = lambda: True
    p._session = session
    p._account = "111122223333"
    session.client = lambda name, **kw: ce  # route every client() call to the stubbed one
    items = p.fetch_costs(date(2026, 10, 1), date(2026, 10, 2))
    assert [i.cost_usd for i in items] == [5.0, 7.0]
    assert items[0].environment == "development" and p.api_calls == 2
