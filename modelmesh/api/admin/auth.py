"""JWT-based admin authentication.

Two dependencies:
  require_jwt      — valid token, must_change_pw must be False
  require_jwt_any  — valid token in any state (used by change-password)
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)

_logger = logging.getLogger(__name__)

_jwt_secret_env = os.environ.get("JWT_SECRET")
if not _jwt_secret_env:
    _logger.warning(
        "JWT_SECRET env var not set — using a random secret. "
        "All tokens will be invalidated on restart."
    )
_JWT_SECRET: str = _jwt_secret_env or secrets.token_hex(32)
_ALGORITHM = "HS256"
_EXPIRY_HOURS = 8


def create_token(username: str, must_change_pw: bool) -> str:
    payload = {
        "sub": username,
        "must_change_pw": must_change_pw,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])


async def require_jwt(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict:
    """Requires a valid token where must_change_pw is False."""
    payload = _validate(credentials)
    if payload.get("must_change_pw"):
        raise HTTPException(status_code=403, detail="password_change_required")
    return payload


async def require_jwt_any(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> dict:
    """Requires a valid token in any state — used by change-password endpoint."""
    return _validate(credentials)


def _validate(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    try:
        return decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
