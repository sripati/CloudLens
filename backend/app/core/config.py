"""Application configuration.

All settings are read from environment variables (or a `.env` file).
See `.env.example` at the repository root for the full list with comments.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

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

    # ---- Data ---------------------------------------------------------
    # Every cloud starts in Mock mode. Live connections are set up on the Cloud Accounts screen and
    # stored in the database, so nothing about them belongs in this file or in .env.
    ENABLED_PROVIDERS: str = "aws,azure,gcp"
    BACKFILL_DAYS: int = 365  # history loaded on first start (missing older days are added on restart)
    SYNC_LOOKBACK_DAYS: int = 3  # days re-fetched on each daily sync (providers restate recent costs)

    # ---- Scheduler -----------------------------------------------------
    SCHEDULER_ENABLED: bool = True
    DAILY_SYNC_HOUR: int = 2
    DAILY_SYNC_MINUTE: int = 0
    METRICS_INTERVAL_MINUTES: int = 5
    INTRADAY_COST_REFRESH_MINUTES: int = 15
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
    # bundled test inbox, used until real webhook URLs are saved on the Settings screen
    SLACK_WEBHOOK_URL: str = "http://mock-receiver:9000/slack"
    TEAMS_WEBHOOK_URL: str = "http://mock-receiver:9000/teams"
    ALERTMANAGER_SHARED_DIR: str = "/shared"  # volume where the backend leaves the Slack URL for Alertmanager
    DEFAULT_NOTIFICATION_CHANNEL: str = "both"  # slack | teams | both
    DASHBOARD_PUBLIC_URL: str = "http://localhost:8080"

    # ---- Business defaults (editable later in Settings screen) ---------
    DEFAULT_MONTHLY_BUDGET_USD: float = 120000.0
    DEFAULT_EXCHANGE_RATE_INR: float = 84.20

    @property
    def enabled_providers(self) -> List[str]:
        return [p.strip().lower() for p in self.ENABLED_PROVIDERS.split(",") if p.strip()]

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
