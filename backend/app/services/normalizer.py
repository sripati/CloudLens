"""Normalization rules that turn provider-specific values into the unified CloudLens vocabulary.

* resource_type  : compute | containers | database | storage | networking | other
* environment    : production | staging | development | unassigned
"""
from __future__ import annotations

import re
from typing import Optional

RESOURCE_TYPES = ["compute", "containers", "database", "storage", "networking", "other"]
ENVIRONMENTS = ["production", "staging", "development", "unassigned"]
PROVIDERS = ["aws", "azure", "gcp"]

# Ordered (pattern, type) pairs: first match wins. Patterns are matched case-insensitively
# against the provider's service name (AWS SERVICE dimension, Azure ServiceName, GCP service.description).
_SERVICE_RULES = [
    # containers first so "Elastic Kubernetes" doesn't match "Elastic Compute"
    (r"kubernetes|\beks\b|\baks\b|\bgke\b|container|ecs|fargate|cloud run|openshift", "containers"),
    (r"relational database|\brds\b|dynamodb|aurora|redshift|elasticache|documentdb|sql|cosmos|"
     r"bigquery|bigtable|spanner|firestore|datastore|memorystore|database|redis", "database"),
    (r"simple storage|\bs3\b|glacier|elastic block|\bebs\b|efs|storage|backup|blob|files|disk|filestore", "storage"),
    (r"data transfer|cloudfront|route ?53|vpc|virtual network|load balanc|nat gateway|bandwidth|"
     r"networking|network|cdn|dns|api gateway|front door|application gateway|interconnect|vpn", "networking"),
    (r"elastic compute|\bec2\b|lambda|compute engine|virtual machine|app service|functions|"
     r"lightsail|batch|compute|sagemaker|vertex|machine learning", "compute"),
]

_ENV_ALIASES = {
    "production": {"prod", "production", "prd", "live", "prod-1"},
    "staging": {"stg", "stage", "staging", "uat", "preprod", "pre-prod", "qa"},
    "development": {"dev", "development", "test", "testing", "sandbox", "sbx", "local"},
}


def classify_service(service: str) -> str:
    name = (service or "").lower()
    for pattern, rtype in _SERVICE_RULES:
        if re.search(pattern, name):
            return rtype
    return "other"


def normalize_environment(value: Optional[str]) -> str:
    if not value:
        return "unassigned"
    v = value.strip().lower()
    # AWS Cost Explorer returns tag groups as "environment$prod"
    if "$" in v:
        v = v.split("$", 1)[1]
    if not v:
        return "unassigned"
    for env, aliases in _ENV_ALIASES.items():
        if v in aliases:
            return env
    for env, aliases in _ENV_ALIASES.items():
        if any(a in v for a in aliases):
            return env
    return "unassigned"


def normalize_region(value: Optional[str]) -> str:
    v = (value or "").strip().lower()
    if not v or v in {"no region", "global", "unknown", "none"}:
        return "global"
    return v[:40]


def to_usd(amount: float, currency: str, inr_rate: float, conversion_rate: Optional[float] = None) -> float:
    """Convert an amount in the billing currency into USD.

    `conversion_rate` (GCP billing export) is billing-currency units per USD.
    """
    currency = (currency or "USD").upper()
    if currency == "USD":
        return float(amount)
    if conversion_rate:
        return float(amount) / float(conversion_rate)
    if currency == "INR" and inr_rate:
        return float(amount) / float(inr_rate)
    return float(amount)
