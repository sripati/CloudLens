"""CloudLens API entry point.

Run locally:   uvicorn app.main:app --reload
API docs:      http://localhost:8000/docs  (Swagger UI)  |  /redoc
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.routes import alerts, auth, cloud_accounts, costs, dashboard, reports, resources, settings, sync
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.services import cloud_accounts as cloud_accounts_service
from app.services import prom_metrics, scheduler, settings_service
from app.services.seed import seed

s = get_settings()
logging.basicConfig(level=s.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("cloudlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed(db)
        settings_service.publish_alertmanager_slack_url(db)
    finally:
        db.close()
    scheduler.start()
    log.info("CloudLens started (ALERT_DELIVERY=%s)", s.ALERT_DELIVERY)
    yield
    scheduler.shutdown()


app = FastAPI(
    title="CloudLens API",
    description="DevOps dashboard for multi-cloud (AWS, Azure, GCP) resource and cost monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    if path not in ("/metrics", "/health"):
        prom_metrics.http_requests.labels(request.method, path, str(response.status_code)).inc()
        prom_metrics.http_latency.labels(request.method, path).observe(time.perf_counter() - start)
    return response


for r in (auth.router, dashboard.router, costs.router, resources.router, alerts.router, sync.router, settings.router, reports.router, cloud_accounts.router):
    app.include_router(r, prefix=s.API_PREFIX)


@app.get("/health", tags=["system"])
def health():
    db = SessionLocal()
    source = "mock"
    try:
        db.execute(text("SELECT 1"))
        source = cloud_accounts_service.summary(db)
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    body = {"status": "ok" if db_ok else "degraded", "database": db_ok, "data_source": source, "version": app.version}
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.get("/metrics", tags=["system"], include_in_schema=False)
def metrics():
    return Response(generate_latest(prom_metrics.REGISTRY), media_type=CONTENT_TYPE_LATEST)
