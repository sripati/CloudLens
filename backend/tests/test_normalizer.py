import pytest

from app.services.normalizer import classify_service, normalize_environment, normalize_region, to_usd


@pytest.mark.parametrize(
    "service,expected",
    [
        ("Amazon Elastic Compute Cloud - Compute", "compute"),
        ("Amazon Elastic Kubernetes Service", "containers"),
        ("Amazon Relational Database Service", "database"),
        ("Amazon Simple Storage Service", "storage"),
        ("AWS Data Transfer", "networking"),
        ("Virtual Machines", "compute"),
        ("Azure Kubernetes Service", "containers"),
        ("SQL Database", "database"),
        ("Storage", "storage"),
        ("Bandwidth", "networking"),
        ("Compute Engine", "compute"),
        ("Kubernetes Engine", "containers"),
        ("BigQuery", "database"),
        ("Cloud Storage", "storage"),
        ("AWS Support (Business)", "other"),
        ("", "other"),
    ],
)
def test_classify_service(service, expected):
    assert classify_service(service) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("prod", "production"), ("Production", "production"), ("environment$prod", "production"),
        ("stg", "staging"), ("UAT", "staging"), ("dev", "development"), ("test", "development"),
        ("environment$", "unassigned"), (None, "unassigned"), ("", "unassigned"), ("marketing", "unassigned"),
        ("prod-eu", "production"),
    ],
)
def test_normalize_environment(value, expected):
    assert normalize_environment(value) == expected


def test_normalize_region():
    assert normalize_region("No Region") == "global"
    assert normalize_region("CentralIndia") == "centralindia"
    assert normalize_region(None) == "global"


def test_currency_conversion():
    assert to_usd(100, "USD", 84) == 100
    assert to_usd(842, "INR", 84.2) == pytest.approx(10)
    # GCP export provides its own conversion rate (billing currency per USD)
    assert to_usd(830, "INR", 84.2, conversion_rate=83.0) == pytest.approx(10)
