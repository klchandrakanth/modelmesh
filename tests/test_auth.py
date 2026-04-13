import bcrypt
import pytest
from pathlib import Path
from fastapi import HTTPException

from modelmesh.auth.api_keys import ApiKeyManager, configure_auth, require_api_key


# Low rounds (4) so tests finish quickly
TEST_SECRET = "dev-secret-local"
TEST_HASHED = bcrypt.hashpw(TEST_SECRET.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture
def keys_yaml(tmp_path: Path) -> Path:
    content = f"""
keys:
  - id: key-1
    name: Test Key
    hashed: "{TEST_HASHED}"
    rate_limit_per_minute: 60
"""
    p = tmp_path / "keys.yaml"
    p.write_text(content)
    return p


def test_manager_loads_keys(keys_yaml):
    manager = ApiKeyManager(keys_yaml)
    assert manager.has_keys


def test_manager_empty_when_file_missing(tmp_path):
    manager = ApiKeyManager(tmp_path / "nonexistent.yaml")
    assert not manager.has_keys


def test_validate_correct_key(keys_yaml):
    manager = ApiKeyManager(keys_yaml)
    entry = manager.validate(TEST_SECRET)
    assert entry.id == "key-1"


def test_validate_wrong_key_raises(keys_yaml):
    manager = ApiKeyManager(keys_yaml)
    with pytest.raises(HTTPException) as exc:
        manager.validate("wrong-key")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_api_key_passes_when_auth_disabled(keys_yaml):
    manager = ApiKeyManager(keys_yaml)
    configure_auth(manager, enabled=False)

    from starlette.testclient import TestClient
    from starlette.requests import Request
    from starlette.datastructures import Headers
    import io

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    result = await require_api_key(request)
    assert result is None


@pytest.mark.asyncio
async def test_require_api_key_rejects_missing_key_when_enabled(keys_yaml):
    manager = ApiKeyManager(keys_yaml)
    configure_auth(manager, enabled=True)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [],
        "query_string": b"",
    }
    from starlette.requests import Request
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        await require_api_key(request)
    assert exc.value.status_code == 401
