"""Database engine, session factory and declarative base (SQLAlchemy 2.0)."""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {"echo": get_settings().DB_ECHO, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_size"] = get_settings().DB_POOL_SIZE
        kwargs["max_overflow"] = 5
    return create_engine(url, **kwargs)


engine = _make_engine(get_settings().DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_engine(url: str) -> None:
    """Re-point the global engine (used by tests)."""
    global engine
    engine = _make_engine(url)
    SessionLocal.configure(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables if they do not exist."""
    from app import models  # noqa: F401  (register models)

    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)


def add_missing_columns(bind) -> None:
    """create_all never alters existing tables, so schema changes after the first release go here."""
    resources = {c["name"] for c in inspect(bind).get_columns("resources")}
    sync_runs = {c["name"] for c in inspect(bind).get_columns("sync_runs")}
    accounts = {c["name"] for c in inspect(bind).get_columns("cloud_accounts")} if inspect(bind).has_table("cloud_accounts") else set()
    with bind.begin() as conn:
        if "source" not in resources:  # everything collected before modes existed is mock data
            conn.execute(text("ALTER TABLE resources ADD COLUMN source VARCHAR(10) NOT NULL DEFAULT 'mock'"))
        if "environment" not in sync_runs:
            conn.execute(text("ALTER TABLE sync_runs ADD COLUMN environment VARCHAR(20) NOT NULL DEFAULT ''"))
        # connection settings moved to cloud_connections, one row per environment
        for column in sorted(accounts - {"provider", "mode", "updated_at"}):
            conn.execute(text(f"ALTER TABLE cloud_accounts DROP COLUMN {column}"))
