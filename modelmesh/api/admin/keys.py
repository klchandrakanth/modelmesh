"""GET /admin/keys — list API keys (masked, no hashes exposed).

POST /admin/keys — generate a new key (plaintext returned once, hash stored).
DELETE /admin/keys/{key_id} — revoke a key.
"""
from __future__ import annotations

import asyncio
import secrets
from pathlib import Path

import bcrypt
import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modelmesh.api.admin.auth import require_jwt
from modelmesh.config.settings import settings

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateKeyRequest(BaseModel):
    name: str
    rate_limit_per_minute: int = 60


async def _load_keys() -> list[dict]:
    path = settings.keys_config_path

    def _read():
        if not path.exists():
            return []
        data = yaml.safe_load(path.read_text()) or {}
        return data.get("keys", [])

    return await asyncio.to_thread(_read)


async def _save_keys(keys: list[dict]) -> None:
    path = settings.keys_config_path

    def _write():
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = yaml.safe_load(path.read_text()) if path.exists() else {}
        if not isinstance(existing, dict):
            existing = {}
        existing["keys"] = keys
        path.write_text(yaml.dump(existing, default_flow_style=False, allow_unicode=True))

    await asyncio.to_thread(_write)


@router.get("/keys", dependencies=[Depends(require_jwt)])
async def list_keys():
    keys = await _load_keys()
    return {
        "keys": [
            {
                "id": k["id"],
                "name": k.get("name", k["id"]),
                "rate_limit_per_minute": k.get("rate_limit_per_minute", 60),
                "routing_policy": k.get("routing_policy", {}),
            }
            for k in keys
        ]
    }


@router.post("/keys", dependencies=[Depends(require_jwt)], status_code=201)
async def create_key(body: CreateKeyRequest):
    raw = secrets.token_urlsafe(32)
    hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
    key_id = f"key-{secrets.token_hex(4)}"

    keys = await _load_keys()
    keys.append(
        {
            "id": key_id,
            "name": body.name,
            "hashed": hashed,
            "rate_limit_per_minute": body.rate_limit_per_minute,
        }
    )
    await _save_keys(keys)

    return {
        "id": key_id,
        "name": body.name,
        "secret": raw,  # returned ONCE — not stored in plaintext
        "rate_limit_per_minute": body.rate_limit_per_minute,
        "warning": "Store this secret safely — it cannot be retrieved again.",
    }


@router.delete("/keys/{key_id}", dependencies=[Depends(require_jwt)])
async def revoke_key(key_id: str):
    keys = await _load_keys()
    updated = [k for k in keys if k["id"] != key_id]
    if len(updated) == len(keys):
        raise HTTPException(status_code=404, detail=f"Key {key_id!r} not found")
    await _save_keys(updated)
    return {"deleted": key_id}
