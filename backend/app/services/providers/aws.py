"""AWS connector.

* Costs     : Cost Explorer `GetCostAndUsage` (DAILY, UnblendedCost, grouped by SERVICE, limited to this account)
* Inventory : EC2 `DescribeInstances` and RDS `DescribeDBInstances` per configured region
* Metrics   : CloudWatch `GetMetricData` (CPUUtilization)

Cost note: Cost Explorer costs USD 0.01 per request, so the scheduler only re-fetches the last
SYNC_LOOKBACK_DAYS days and intraday refreshes should be spaced out (INTRADAY_COST_REFRESH_MINUTES).
Required IAM permissions: ce:GetCostAndUsage, ec2:DescribeInstances, rds:DescribeDBInstances,
cloudwatch:GetMetricData, cloudwatch:ListMetrics, sts:GetCallerIdentity (see docs/modules/providers.md).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services.normalizer import classify_service, normalize_environment, to_usd
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


def cost_explorer_period(start: date, end: date, utc_today: date) -> Optional[Tuple[date, date]]:
    """Clamp a requested range to what Cost Explorer accepts, or None when nothing is left.

    It keeps about 13 months of history and rejects an end date past the start of next month. Its days
    are UTC, so "tomorrow" in a timezone ahead of UTC can be out of range on the last day of a month.
    """
    oldest = (utc_today.replace(day=1) - timedelta(days=380)).replace(day=1)
    start, end = max(start, oldest), min(end, utc_today + timedelta(days=1))
    return (start, end) if start < end else None


def _tags(raw: Optional[List[Dict[str, str]]]) -> Dict[str, str]:
    return {t["Key"]: t["Value"] for t in (raw or []) if "Key" in t}


class AWSProvider(CloudProvider):
    name = "aws"
    display_name = "Amazon Web Services"

    def __init__(self, inr_rate: float = 84.2, config: Optional[Dict[str, str]] = None):
        super().__init__()
        self.c = config or {}
        self.environment = self.c.get("environment", "")
        self.inr_rate = inr_rate
        self._session = None
        self._account: Optional[str] = None

    @property
    def regions(self) -> List[str]:
        return [r.strip() for r in self.c.get("regions", "").split(",") if r.strip()]

    def is_configured(self) -> bool:
        return self.c.get("auth_method") == "default_chain" or bool(self.c.get("access_key_id") and self.c.get("secret_access_key"))

    def session(self):
        if not self.is_configured():
            raise ProviderNotConfigured("AWS credentials missing (access key and secret key, or the EC2 instance role)")
        if self._session is None:
            import boto3

            if self.c.get("auth_method") == "default_chain":
                self._session = boto3.Session()  # EC2 instance role
            else:
                self._session = boto3.Session(
                    aws_access_key_id=self.c["access_key_id"],
                    aws_secret_access_key=self.c["secret_access_key"],
                    aws_session_token=self.c.get("session_token") or None,
                )
        return self._session

    def secret_values(self) -> List[str]:
        return [self.c.get("secret_access_key", ""), self.c.get("session_token", "")]

    def hint(self, exc: Exception) -> str:
        response = getattr(exc, "response", None)
        code = response.get("Error", {}).get("Code", "") if isinstance(response, dict) else ""
        message = str(exc).lower()
        if code in ("InvalidClientTokenId", "SignatureDoesNotMatch", "UnrecognizedClientException", "ExpiredToken") or type(exc).__name__ in ("NoCredentialsError", "PartialCredentialsError"):
            return "AWS rejected these credentials. Check the access key, secret key and session token."
        if "not enabled for cost explorer" in message or code == "DataUnavailableException":
            return "Cost Explorer is not enabled or has no data yet. Enable it in the AWS Billing console; first activation can take up to 24 hours."
        if "accessdenied" in code.lower() or "unauthorized" in code.lower():
            return "This identity lacks the permission. Attach deploy/aws/iam-policy.json to it."
        return ""

    def account_id(self) -> str:
        if self._account is None:
            self.api_calls += 1
            # region is required when the environment sets no default (for example in the Docker image)
            self._account = self.session().client("sts", region_name=self.c["cost_explorer_region"]).get_caller_identity()["Account"]
        return self._account

    def fetch_costs(self, start: date, end: date) -> List[CostItem]:
        period = cost_explorer_period(start, end, datetime.now(timezone.utc).date())
        if period is None:
            return []
        start, end = period
        ce = self.session().client("ce", region_name=self.c["cost_explorer_region"])
        params: Dict[str, Any] = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost", "UsageQuantity"],
            "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
            # a management account also sees its member accounts, which may be other environments' connections
            "Filter": {"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [self.account_id()]}},
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
        items = parse_cost_explorer(pages, self.account_id(), self.inr_rate)
        for item in items:
            item.environment = self.environment
        return items

    def fetch_resources(self) -> List[ResourceItem]:
        out: List[ResourceItem] = []
        acct = self.account_id()
        for region in self.regions:
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
                                environment=self.environment,
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
                            resource_id=db.get("DBInstanceArn") or db["DBInstanceIdentifier"],  # identifiers repeat across accounts
                            name=db["DBInstanceIdentifier"],
                            resource_type="database",
                            service="Amazon Relational Database Service",
                            environment=self.environment,
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
                            "Metric": {"Namespace": ns, "MetricName": "CPUUtilization", "Dimensions": [{"Name": dim, "Value": r.resource_id if r.resource_type == "compute" else r.name}]},
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
            return {"ok": False, "message": "AWS credentials not set"}
        region = (self.regions or ["us-east-1"])[0]

        def identity() -> str:
            return f"Account {self.account_id()}"

        def costs() -> str:
            ce = self.session().client("ce", region_name=self.c["cost_explorer_region"])
            today = datetime.now(timezone.utc).date()
            self.api_calls += 1
            ce.get_cost_and_usage(
                TimePeriod={"Start": (today - timedelta(days=1)).isoformat(), "End": today.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )
            return "Cost data is readable"

        def ec2() -> str:
            self.api_calls += 1
            self.session().client("ec2", region_name=region).describe_instances(MaxResults=5)
            return f"Instances readable in {region}"

        def rds() -> str:
            self.api_calls += 1
            self.session().client("rds", region_name=region).describe_db_instances(MaxRecords=20)
            return f"Databases readable in {region}"

        def cloudwatch() -> str:
            self.api_calls += 1
            self.session().client("cloudwatch", region_name=region).list_metrics(Namespace="AWS/EC2")
            return f"Metrics readable in {region}"

        return self.run_checks([
            ("Sign in (STS)", identity), ("Cost Explorer", costs), ("EC2 inventory", ec2), ("RDS inventory", rds), ("CloudWatch metrics", cloudwatch),
        ])
