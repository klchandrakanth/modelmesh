"""Create tables and seed initial data on first startup."""
from __future__ import annotations

from pathlib import Path

import asyncpg
import yaml
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    must_change_pw BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_CREATE_MODELS = """
CREATE TABLE IF NOT EXISTS models (
    name           TEXT PRIMARY KEY,
    provider       TEXT NOT NULL,
    context_window INTEGER NOT NULL DEFAULT 4096,
    cost_per_1k    REAL NOT NULL DEFAULT 0.0,
    is_default     BOOLEAN NOT NULL DEFAULT FALSE,
    is_fallback    BOOLEAN NOT NULL DEFAULT FALSE,
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


async def init_schema(pool: asyncpg.Pool, models_yaml: Path) -> None:
    """Create tables and seed if empty. Safe to call on every startup."""
    async with pool.acquire() as conn:
        await conn.execute(_CREATE_USERS)
        await conn.execute(_CREATE_MODELS)
        await _seed_admin(conn)
        await _seed_models(conn, models_yaml)


async def _seed_admin(conn: asyncpg.Connection) -> None:
    count = await conn.fetchval("SELECT COUNT(*) FROM users")
    if count == 0:
        pw_hash = pwd_context.hash("admin")
        await conn.execute(
            "INSERT INTO users (username, password_hash, must_change_pw) VALUES ($1, $2, TRUE)",
            "admin",
            pw_hash,
        )


async def _seed_models(conn: asyncpg.Connection, models_yaml: Path) -> None:
    count = await conn.fetchval("SELECT COUNT(*) FROM models")
    if count != 0 or not models_yaml.exists():
        return
    data = yaml.safe_load(models_yaml.read_text())
    defaults = data.get("defaults", {})
    default_chat = defaults.get("chat", "")
    default_fallback = defaults.get("fallback", "")
    for name, attrs in data.get("models", {}).items():
        await conn.execute(
            """
            INSERT INTO models (name, provider, context_window, cost_per_1k, is_default, is_fallback)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            name,
            attrs["provider"],
            attrs.get("context_window", 4096),
            float(attrs.get("cost_per_1k_tokens", 0.0)),
            name == default_chat,
            name == default_fallback,
        )
