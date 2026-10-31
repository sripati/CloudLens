"""Test fixtures.

By default tests use an in-memory SQLite database. To run against PostgreSQL:
    TEST_DATABASE_URL=postgresql+psycopg://cloudlens:cloudlens@localhost:5432/cloudlens_test pytest
"""
import os

os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ.update({
    "SCHEDULER_ENABLED": "false",
    "ALERT_DELIVERY": "direct",
    "BACKFILL_DAYS": "60",
    "ALERTMANAGER_WEBHOOK_TOKEN": "test-token",
    "SLACK_WEBHOOK_URL": "http://mock-receiver.invalid/slack",
    "TEAMS_WEBHOOK_URL": "http://mock-receiver.invalid/teams",
    "ADMIN_EMAIL": "admin@test.dev",
    "ADMIN_PASSWORD": "Admin@123",
    "VIEWER_EMAIL": "viewer@test.dev",
    "VIEWER_PASSWORD": "Viewer@123",
    "JWT_SECRET": "test-secret-key-with-at-least-32-bytes!!",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.services import notifier  # noqa: E402

SENT = []


@pytest.fixture(autouse=True)
def fake_notifier(monkeypatch):
    """Capture notifications instead of calling real webhooks."""
    SENT.clear()

    def fake_send(channels, title, message, severity, status, fields, urls):
        SENT.append({"channels": channels, "title": title, "severity": severity, "status": status})
        return ("sent", "") if channels else ("skipped", "no channel selected")

    monkeypatch.setattr(notifier, "send", fake_send)
    yield SENT


@pytest.fixture(scope="session")
def seeded():
    """Fresh schema + seed + 60 days of mock history, shared by the whole session."""
    from app import models  # noqa: F401
    from app.services.ingestion import run_job
    from app.services.seed import seed

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed(db)
    run_job(db, "backfill", triggered_by="test")
    db.close()
    yield True


@pytest.fixture
def db(seeded):
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
def client(seeded):
    from app.main import app

    with TestClient(app) as c:
        yield c


def _token(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _token(client, "admin@test.dev", "Admin@123")


@pytest.fixture(scope="session")
def viewer_headers(client):
    return _token(client, "viewer@test.dev", "Viewer@123")
