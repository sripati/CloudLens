"""Application configuration.

All settings are read from environment variables (or a `.env` file).
See `.env.example` at the repository root for the full list with comments.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # ---- General -------------------------------------------------------
    APP_NAME: str = "CloudLens"
    APP_ENV: str = "development"  # development | staging | production
    LOG_LEVEL: str = "INFO"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080,http://localhost"
    TIMEZONE: str = "Asia/Kolkata"

    # ---- Database ------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg://cloudlens:cloudlens@localhost:5432/cloudlens"
    DB_POOL_SIZE: int = 5
    DB_ECHO: bool = False

    # ---- Auth ----------------------------------------------------------
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    ADMIN_EMAIL: str = "admin@cloudlens.dev"
    ADMIN_PASSWORD: str = "Admin@123"
    ADMIN_NAME: str = "Administrator"
    VIEWER_EMAIL: str = "viewer@cloudlens.dev"
    VIEWER_PASSWORD: str = "Viewer@123"
    VIEWER_NAME: str = "Read-only Viewer"

    # ---- Data source switch -------------------------------------------
    # mock -> built-in deterministic data generator (no cloud credentials needed)
    # live -> real AWS / Azure / GCP APIs using the credentials below
    DATA_SOURCE: str = "mock"
    ENABLED_PROVIDERS: str = "aws,azure,gcp"
    ENV_TAG_KEY: str = "environment"  # tag/label key that holds production/staging/development
    BACKFILL_DAYS: int = 365  # history loaded on first start (missing older days are added on restart)
    SYNC_LOOKBACK_DAYS: int = 3  # days re-fetched on each daily sync (providers restate recent costs)

    # ---- AWS -----------------------------------------------------------
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_SESSION_TOKEN: str = ""
    AWS_PROFILE: str = ""
    # true -> use the default boto3 credential chain (EC2 instance role / ECS task role); recommended on EC2
    AWS_USE_DEFAULT_CREDENTIALS: bool = False
    AWS_REGIONS: str = "ap-south-1"
    AWS_COST_EXPLORER_REGION: str = "us-east-1"

    # ---- Azure ---------------------------------------------------------
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_SUBSCRIPTION_ID: str = ""

    # ---- GCP -----------------------------------------------------------
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GCP_PROJECT_ID: str = ""
    GCP_BILLING_ACCOUNT_ID: str = ""
    GCP_BILLING_EXPORT_TABLE: str = ""  # project.dataset.gcp_billing_export_v1_XXXX

    # ---- Scheduler -----------------------------------------------------
    SCHEDULER_ENABLED: bool = True
    DAILY_SYNC_HOUR: int = 2
    DAILY_SYNC_MINUTE: int = 0
    METRICS_INTERVAL_MINUTES: int = 5
    INTRADAY_COST_REFRESH_MINUTES: int = 15  # use 360+ in live mode (AWS charges per Cost Explorer request)
    ALERT_EVAL_INTERVAL_SECONDS: int = 60
    METRICS_RETENTION_DAYS: int = 90
    COST_RETENTION_DAYS: int = 730

    # ---- Alerting ------------------------------------------------------
    # alertmanager -> rule state is exported to Prometheus, Alertmanager calls our webhook
    # direct       -> the backend sends notifications itself (useful without Docker)
    ALERT_DELIVERY: str = "alertmanager"
    ALERTMANAGER_WEBHOOK_TOKEN: str = "change-me-webhook-token"
    ALERTMANAGER_URL: str = "http://alertmanager:9093"
    PROMETHEUS_URL: str = "http://prometheus:9090"
    SLACK_WEBHOOK_URL: str = "http://mock-receiver:9000/slack"
    TEAMS_WEBHOOK_URL: str = "http://mock-receiver:9000/teams"
    DEFAULT_NOTIFICATION_CHANNEL: str = "both"  # slack | teams | both
    DASHBOARD_PUBLIC_URL: str = "http://localhost:8080"

    # ---- Business defaults (editable later in Settings screen) ---------
    DEFAULT_MONTHLY_BUDGET_USD: float = 120000.0
    DEFAULT_EXCHANGE_RATE_INR: float = 84.20

    @field_validator("DATA_SOURCE")
    @classmethod
    def _check_source(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"mock", "live"}:
            raise ValueError("DATA_SOURCE must be 'mock' or 'live'")
        return v

    @property
    def enabled_providers(self) -> List[str]:
        return [p.strip().lower() for p in self.ENABLED_PROVIDERS.split(",") if p.strip()]

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def aws_regions(self) -> List[str]:
        return [r.strip() for r in self.AWS_REGIONS.split(",") if r.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
