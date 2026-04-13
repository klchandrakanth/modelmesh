"""API key authentication for ModelMesh.

Keys are stored in config/keys.yaml as bcrypt hashes.
Auth is optional — if enable_auth=False (default), all requests pass through.

Usage in FastAPI:
    from modelmesh.auth.api_keys import require_api_key
    # Apply as a dependency:
    @router.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import bcrypt
import yaml
from fastapi import HTTPException, Request
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass
class KeyEntry:
    """A single API key entry loaded from keys.yaml."""

    id: str
    name: str
    hashed: str
    rate_limit_per_minute: int = 60
    routing_policy: dict = field(default_factory=dict)


class ApiKeyManager:
    """Loads and validates API keys from a YAML file."""

    def __init__(self, config_path: Path) -> None:
        self._entries: list[KeyEntry] = []
        if config_path.exists():
            self._entries = self._load(config_path)

    @staticmethod
    def _load(path: Path) -> list[KeyEntry]:
        data = yaml.safe_load(path.read_text()) or {}
        return [
            KeyEntry(
                id=k["id"],
                name=k.get("name", k["id"]),
                hashed=k["hashed"],
                rate_limit_per_minute=k.get("rate_limit_per_minute", 60),
                routing_policy=k.get("routing_policy", {}),
            )
            for k in data.get("keys", [])
        ]

    def validate(self, raw_key: str) -> KeyEntry:
        """Return the matching KeyEntry or raise HTTPException(401)."""
        raw_bytes = raw_key.encode("utf-8")
        for entry in self._entries:
            if bcrypt.checkpw(raw_bytes, entry.hashed.encode("utf-8")):
                return entry
        raise HTTPException(status_code=401, detail="Invalid API key")

    @property
    def has_keys(self) -> bool:
        """True if at least one key is configured."""
        return bool(self._entries)


# Module-level state — replaced by main.py on startup
_manager: Optional[ApiKeyManager] = None
_auth_enabled: bool = False


def configure_auth(manager: ApiKeyManager, enabled: bool) -> None:
    """Wire the auth manager and toggle enforcement."""
    global _manager, _auth_enabled  # noqa: PLW0603
    _manager = manager
    _auth_enabled = enabled


async def require_api_key(request: Request) -> Optional[KeyEntry]:
    """FastAPI dependency. Returns KeyEntry if auth enabled, else None."""
    if not _auth_enabled:
        return None

    raw = request.headers.get("X-API-Key") or (
        request.headers.get("Authorization", "").removeprefix("Bearer ")
    )
    if not raw:
        raise HTTPException(status_code=401, detail="Missing API key")

    assert _manager is not None
    return _manager.validate(raw)
