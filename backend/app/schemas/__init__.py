"""Pydantic request / response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.alert import ALERT_METRICS, CHANNELS, OPERATORS, SEVERITIES
from app.services.normalizer import ENVIRONMENTS, PROVIDERS, RESOURCE_TYPES

Role = Literal["admin", "viewer"]


# ---------------------------------------------------------------- auth / users
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(default="", max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role = "viewer"


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------- alerts
class AlertRuleIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=1000)
    metric: str
    provider: Optional[str] = None
    environment: Optional[str] = None
    resource_type: Optional[str] = None
    operator: str = ">"
    threshold: float
    severity: str = "warning"
    channels: str = "default"
    enabled: bool = True

    @field_validator("metric")
    @classmethod
    def _metric(cls, v):
        if v not in ALERT_METRICS:
            raise ValueError(f"metric must be one of {sorted(ALERT_METRICS)}")
        return v

    @field_validator("operator")
    @classmethod
    def _op(cls, v):
        if v not in OPERATORS:
            raise ValueError(f"operator must be one of {sorted(OPERATORS)}")
        return v

    @field_validator("severity")
    @classmethod
    def _sev(cls, v):
        if v not in SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(SEVERITIES)}")
        return v

    @field_validator("channels")
    @classmethod
    def _ch(cls, v):
        if v not in CHANNELS:
            raise ValueError(f"channels must be one of {sorted(CHANNELS)}")
        return v

    @field_validator("provider", "environment", "resource_type", mode="before")
    @classmethod
    def _blank(cls, v):
        return v or None

    @field_validator("provider")
    @classmethod
    def _prov(cls, v):
        if v and v not in PROVIDERS:
            raise ValueError("unknown provider")
        return v

    @field_validator("environment")
    @classmethod
    def _env(cls, v):
        if v and v not in ENVIRONMENTS:
            raise ValueError("unknown environment")
        return v

    @field_validator("resource_type")
    @classmethod
    def _rt(cls, v):
        if v and v not in RESOURCE_TYPES:
            raise ValueError("unknown resource type")
        return v


class AlertRuleOut(AlertRuleIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    state: str
    last_value: Optional[float] = None
    last_detail: str = ""
    last_evaluated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AlertEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_id: Optional[int]
    status: str
    severity: str
    title: str
    message: str
    value: Optional[float]
    threshold: Optional[float]
    labels: Dict[str, Any]
    source: str
    starts_at: datetime
    ends_at: Optional[datetime]
    notified_channels: str
    notification_status: str
    notification_error: str
    acknowledged: bool
    created_at: datetime


class TestNotification(BaseModel):
    channel: Literal["slack", "teams", "both", "default"] = "default"
    message: str = Field(default="This is a test notification from CloudLens.", max_length=500)


# ---------------------------------------------------------------- settings / sync
class SettingsUpdate(BaseModel):
    monthly_budget_usd: Optional[float] = Field(default=None, gt=0)
    provider_budgets_usd: Optional[Dict[str, float]] = None
    exchange_rate_inr: Optional[float] = Field(default=None, gt=0)
    default_currency: Optional[Literal["USD", "INR"]] = None
    notification_channel: Optional[Literal["slack", "teams", "both"]] = None
    idle_cpu_threshold: Optional[float] = Field(default=None, ge=0, le=100)
    underutilized_cpu_threshold: Optional[float] = Field(default=None, ge=0, le=100)

    @field_validator("provider_budgets_usd")
    @classmethod
    def _budgets(cls, v):
        if v is None:
            return v
        for k, val in v.items():
            if k not in PROVIDERS or val < 0:
                raise ValueError("provider budgets must use aws/azure/gcp keys and positive values")
        return v


class SyncRequest(BaseModel):
    job: Literal["manual", "daily", "intraday", "metrics", "backfill"] = "manual"
    providers: Optional[List[str]] = None


class MockAnomaly(BaseModel):
    provider: Literal["aws", "azure", "gcp"] = "aws"
    factor: float = Field(default=2.5, gt=1, le=10)
    days_ago: int = Field(default=1, ge=0, le=30)
