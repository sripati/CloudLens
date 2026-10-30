"""AWS connector.

* Costs     : Cost Explorer `GetCostAndUsage` (DAILY, UnblendedCost, grouped by SERVICE + environment tag)
* Inventory : EC2 `DescribeInstances` and RDS `DescribeDBInstances` per configured region
* Metrics   : CloudWatch `GetMetricData` (CPUUtilization)

Cost note: Cost Explorer costs USD 0.01 per request, so the scheduler only re-fetches the last
SYNC_LOOKBACK_DAYS days and intraday refreshes should be spaced out (INTRADAY_COST_REFRESH_MINUTES).
Required IAM permissions: ce:GetCostAndUsage, ec2:DescribeInstances, rds:DescribeDBInstances,
cloudwatch:GetMetricData, sts:GetCallerIdentity (see docs/modules/providers.md).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.normalizer import classify_service, normalize_environment, normalize_region, to_usd
from app.services.providers.base import CloudProvider, CostItem, MetricItem, ProviderNotConfigured, ResourceItem


def parse_cost_explorer(pages: List[Dict[str, Any]], account_id: str, inr_rate: float) -> List[CostItem]:
    """Convert GetCostAndUsage response pages into CostItems (pure function, unit-tested)."""
    items: List[CostItem] = []
    for page in pages:
        for period in page.get("ResultsByTime", []):
            day = date.fromisoformat(period["TimePeriod"]["Start"])
            for group in period.get("Groups", []):
                keys = group.get("Keys", [])
                service = keys[0] if keys else "Unknown"
                env_key = keys[1] if len(keys) > 1 else ""
                metrics = group.get("Metrics", {})
                cost = metrics.get("UnblendedCost", {})
                amount = float(cost.get("Amount", 0) or 0)
                if amount == 0:
                    continue
                currency = cost.get("Unit", "USD")
                usage = metrics.get("UsageQuantity", {})
                items.append(
                    CostItem(
                        provider="aws",
                        account_id=account_id,
                        usage_date=day,
                        service=service,
                        resource_type=classify_service(service),
                        environment=normalize_environment(env_key),
                        region="global",
                        cost_usd=round(to_usd(amount, currency, inr_rate), 4),
                        cost_original=round(amount, 4),
                        currency_original=currency[:3],
                        usage_quantity=float(usage.get("Amount", 0) or 0),
                        usage_unit=usage.get("Unit", "") or "",
                    )
                )
    return items


def _tags(raw: Optional[List[Dict[str, str]]]) -> Dict[str, str]:
    return {t["Key"]: t["Value"] for t in (raw or []) if "Key" in t}


class AWSProvider(CloudProvider):
    name = "aws"
    display_name = "Amazon Web Services"

    def __init__(self, inr_rate: float = 84.2):
        super().__init__()
        self.s = get_settings()
        self.inr_rate = inr_rate
        self._session = None
        self._account: Optional[str] = None

    def is_configured(self) -> bool:
        return bool((self.s.AWS_ACCESS_KEY_ID and self.s.AWS_SECRET_ACCESS_KEY) or self.s.AWS_PROFILE or self.s.AWS_USE_DEFAULT_CREDENTIALS)

    def session(self):
        if not self.is_configured():
            raise ProviderNotConfigured("AWS credentials missing (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or AWS_PROFILE)")
        if self._session is None:
            import boto3

            if self.s.AWS_PROFILE:
                self._session = boto3.Session(profile_name=self.s.AWS_PROFILE)
            elif self.s.AWS_USE_DEFAULT_CREDENTIALS and not self.s.AWS_ACCESS_KEY_ID:
                self._session = boto3.Session()  # instance role / environment / shared config
            else:
                self._session = boto3.Session(
                    aws_access_key_id=self.s.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=self.s.AWS_SECRET_ACCESS_KEY,
                    aws_session_token=self.s.AWS_SESSION_TOKEN or None,
                )
        return self._session

    def account_id(self) -> str:
        if self._account is None:
            self.api_calls += 1
            self._account = self.session().client("sts").get_caller_identity()["Account"]
        return self._account

    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        ce = self.session().client("ce", region_name=self.s.AWS_COST_EXPLORER_REGION)
        params: Dict[str, Any] = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost", "UsageQuantity"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "TAG", "Key": self.s.ENV_TAG_KEY},
            ],
        }
        pages = []
        while True:
            self.api_calls += 1
            resp = ce.get_cost_and_usage(**params)
            pages.append(resp)
            token = resp.get("NextPageToken")
            if not token:
                break
            params["NextPageToken"] = token
        return parse_cost_explorer(pages, self.account_id(), self.inr_rate)

    def fetch_resources(self) -> List[ResourceItem]:
        out: List[ResourceItem] = []
        acct = self.account_id()
        env_key = self.s.ENV_TAG_KEY
        for region in self.s.aws_regions:
            ec2 = self.session().client("ec2", region_name=region)
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                self.api_calls += 1
                for res in page.get("Reservations", []):
                    for inst in res.get("Instances", []):
                        tags = _tags(inst.get("Tags"))
                        out.append(
                            ResourceItem(
                                provider="aws",
                                account_id=acct,
                                resource_id=inst["InstanceId"],
                                name=tags.get("Name", inst["InstanceId"]),
                                resource_type="compute",
                                service="Amazon Elastic Compute Cloud - Compute",
                                environment=normalize_environment(tags.get(env_key)),
                                region=region,
                                sku=inst.get("InstanceType", ""),
                                status=inst.get("State", {}).get("Name", "unknown"),
                                tags=tags,
                            )
                        )
            rds = self.session().client("rds", region_name=region)
            for page in rds.get_paginator("describe_db_instances").paginate():
                self.api_calls += 1
                for db in page.get("DBInstances", []):
                    tags = _tags(db.get("TagList"))
                    out.append(
                        ResourceItem(
                            provider="aws",
                            account_id=acct,
                            resource_id=db["DBInstanceIdentifier"],
                            name=db["DBInstanceIdentifier"],
                            resource_type="database",
                            service="Amazon Relational Database Service",
                            environment=normalize_environment(tags.get(env_key)),
                            region=region,
                            sku=db.get("DBInstanceClass", ""),
                            status=db.get("DBInstanceStatus", "unknown"),
                            tags=tags,
                        )
                    )
        return out

    def fetch_metrics(self, resources: List[ResourceItem], start: datetime, end: datetime, step_minutes: int = 60) -> List[MetricItem]:
        out: List[MetricItem] = []
        by_region: Dict[str, List[ResourceItem]] = {}
        for r in resources:
            if r.provider == "aws" and r.resource_type in ("compute", "database") and r.status in ("running", "available"):
                by_region.setdefault(r.region, []).append(r)
        for region, items in by_region.items():
            cw = self.session().client("cloudwatch", region_name=region)
            # GetMetricData accepts up to 500 queries per call
            for i in range(0, len(items), 400):
                chunk = items[i : i + 400]
                queries = []
                for idx, r in enumerate(chunk):
                    ns, dim = ("AWS/EC2", "InstanceId") if r.resource_type == "compute" else ("AWS/RDS", "DBInstanceIdentifier")
                    queries.append({
                        "Id": f"m{idx}",
                        "MetricStat": {
                            "Metric": {"Namespace": ns, "MetricName": "CPUUtilization", "Dimensions": [{"Name": dim, "Value": r.resource_id}]},
                            "Period": step_minutes * 60,
                            "Stat": "Average",
                        },
                        "ReturnData": True,
                    })
                token = None
                while True:
                    kwargs: Dict[str, Any] = {"MetricDataQueries": queries, "StartTime": start, "EndTime": end}
                    if token:
                        kwargs["NextToken"] = token
                    self.api_calls += 1
                    resp = cw.get_metric_data(**kwargs)
                    for result in resp.get("MetricDataResults", []):
                        r = chunk[int(result["Id"][1:])]
                        for ts, val in zip(result.get("Timestamps", []), result.get("Values", [])):
                            out.append(MetricItem(provider="aws", resource_id=r.resource_id, ts=ts, cpu_percent=round(float(val), 2)))
                    token = resp.get("NextToken")
                    if not token:
                        break
        return out

    def test_connection(self) -> Dict[str, object]:
        if not self.is_configured():
            return {"ok": False, "message": "AWS credentials not set in .env"}
        try:
            acct = self.account_id()
            ce = self.session().client("ce", region_name=self.s.AWS_COST_EXPLORER_REGION)
            today = date.today()
            self.api_calls += 1
            ce.get_cost_and_usage(
                TimePeriod={"Start": (today - timedelta(days=1)).isoformat(), "End": today.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )
            return {"ok": True, "message": "Cost Explorer reachable", "account": acct}
        except Exception as exc:
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}
