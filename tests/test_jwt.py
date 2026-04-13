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
