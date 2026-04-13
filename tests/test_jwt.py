"""Unit tests for JWT create/decode/verify helpers."""
import pytest
from modelmesh.api.admin.auth import create_token, decode_token


def test_create_and_decode_token():
    token = create_token("admin", must_change_pw=False)
    payload = decode_token(token)
    assert payload["sub"] == "admin"
    assert payload["must_change_pw"] is False


def test_must_change_pw_flag():
    token = create_token("admin", must_change_pw=True)
    payload = decode_token(token)
    assert payload["must_change_pw"] is True


def test_invalid_token_raises():
    import jwt
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("not.a.token")


# --- Additional tests ---

def test_expired_token_raises():
    """Expired tokens must be rejected."""
    import jwt as pyjwt
    from datetime import datetime, timezone, timedelta
    from fastapi import HTTPException
    from modelmesh.api.admin.auth import _JWT_SECRET, _ALGORITHM, require_jwt
    payload = {
        "sub": "admin",
        "must_change_pw": False,
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = pyjwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)
    with pytest.raises(HTTPException) as exc:
        import asyncio
        from fastapi.security import HTTPAuthorizationCredentials
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        asyncio.get_event_loop().run_until_complete(require_jwt(creds))
    assert exc.value.status_code == 401


def test_require_jwt_blocks_must_change_pw():
    """require_jwt must return 403 when must_change_pw is True."""
    import asyncio
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    from modelmesh.api.admin.auth import require_jwt
    token = create_token("admin", must_change_pw=True)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        asyncio.get_event_loop().run_until_complete(require_jwt(creds))
    assert exc.value.status_code == 403
    assert exc.value.detail == "password_change_required"


def test_require_jwt_any_allows_must_change_pw():
    """require_jwt_any must allow tokens with must_change_pw=True."""
    import asyncio
    from fastapi.security import HTTPAuthorizationCredentials
    from modelmesh.api.admin.auth import require_jwt_any
    token = create_token("admin", must_change_pw=True)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    payload = asyncio.get_event_loop().run_until_complete(require_jwt_any(creds))
    assert payload["must_change_pw"] is True


def test_missing_bearer_header_raises_401():
    """Missing Authorization header must return 401."""
    import asyncio
    from fastapi import HTTPException
    from modelmesh.api.admin.auth import require_jwt
    with pytest.raises(HTTPException) as exc:
        asyncio.get_event_loop().run_until_complete(require_jwt(None))
    assert exc.value.status_code == 401
