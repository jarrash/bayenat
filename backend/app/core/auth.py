from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Tenant, User
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    role: str
    email: str
    auth_source: str = "jwt"


def create_access_token(*, user_id: UUID, tenant_id: UUID, role: str, email: str, expires_minutes: int | None = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=expires_minutes or settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "email": email,
        "iat": now,
        "exp": expires,
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _principal_from_claims(claims: dict[str, Any]) -> Principal:
    try:
        return Principal(
            user_id=UUID(str(claims["sub"])),
            tenant_id=UUID(str(claims["tenant_id"])),
            role=str(claims["role"]),
            email=str(claims.get("email", "")),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims") from exc


def decode_access_token(token: str) -> Principal:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], issuer=settings.jwt_issuer)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}) from exc
    return _principal_from_claims(claims)


def _development_principal(db: Session) -> Principal:
    settings = get_settings()
    if not settings.allow_dev_principal or settings.environment not in {"development", "test"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer authentication required", headers={"WWW-Authenticate": "Bearer"})
    tenant = db.query(Tenant).filter(Tenant.name == "Development Tenant").one_or_none()
    if tenant is None:
        tenant = Tenant(name="Development Tenant")
        db.add(tenant)
        db.flush()
    user = db.query(User).filter(User.email == "developer@bayenat.local").one_or_none()
    if user is None:
        user = User(tenant_id=tenant.id, email="developer@bayenat.local", password_hash="development-only", role="ADMIN")
        db.add(user)
        db.flush()
    return Principal(user_id=user.id, tenant_id=tenant.id, role=user.role, email=user.email, auth_source="development")


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None:
        return _development_principal(db)
    return decode_access_token(credentials.credentials)


def _synthetic_development_principal() -> Principal:
    return Principal(user_id=UUID("00000000-0000-0000-0000-000000000001"), tenant_id=UUID("00000000-0000-0000-0000-000000000001"), role="ADMIN", email="developer@bayenat.local", auth_source="development")


def get_request_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credentials is not None:
        return decode_access_token(credentials.credentials)
    settings = get_settings()
    if settings.allow_dev_principal and settings.environment in {"development", "test"}:
        return _synthetic_development_principal()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer authentication required", headers={"WWW-Authenticate": "Bearer"})


def get_websocket_principal(websocket: WebSocket) -> Principal:
    authorization = websocket.headers.get("authorization", "")
    token = authorization.removeprefix("Bearer ").strip()
    token = token or websocket.query_params.get("access_token", "")
    if token:
        return decode_access_token(token)
    settings = get_settings()
    if settings.allow_dev_principal and settings.environment in {"development", "test"}:
        return _synthetic_development_principal()
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer authentication required")


def require_same_tenant(principal: Principal, tenant_id: UUID) -> None:
    if principal.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
