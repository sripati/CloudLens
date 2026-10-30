"""FastAPI dependencies: database session, authentication, role checks, common filters."""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User
from app.services.analytics import Filters
from app.services.ingestion import local_today
from app.services.normalizer import ENVIRONMENTS, PROVIDERS, RESOURCE_TYPES

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired, please sign in again")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user = db.get(User, int(payload.get("sub", 0) or 0))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or disabled")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def _split(value: Optional[str], allowed: Optional[List[str]] = None) -> List[str]:
    if not value or value == "all":
        return []
    items = [v.strip() for v in value.split(",") if v.strip() and v.strip() != "all"]
    if allowed:
        bad = [i for i in items if i not in allowed]
        if bad:
            raise HTTPException(422, f"Invalid filter value(s): {', '.join(bad)}")
    return items


def get_filters(
    start: Optional[date] = Query(None, description="Start date (inclusive), YYYY-MM-DD"),
    end: Optional[date] = Query(None, description="End date (inclusive), YYYY-MM-DD"),
    days: int = Query(30, ge=1, le=730, description="Used when start is not given"),
    provider: Optional[str] = Query(None, description="Comma separated: aws,azure,gcp"),
    environment: Optional[str] = Query(None, description="production,staging,development,unassigned"),
    resource_type: Optional[str] = Query(None, description="compute,containers,database,storage,networking,other"),
    service: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
) -> Filters:
    end = end or local_today()
    start = start or end - timedelta(days=days - 1)
    if start > end:
        raise HTTPException(422, "start must be before end")
    if (end - start).days > 731:
        raise HTTPException(422, "date range limited to 2 years")
    return Filters(
        start=start,
        end=end,
        providers=_split(provider, PROVIDERS),
        environments=_split(environment, ENVIRONMENTS),
        resource_types=_split(resource_type, RESOURCE_TYPES),
        services=_split(service),
        regions=_split(region),
    )
