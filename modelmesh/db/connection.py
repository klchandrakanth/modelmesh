"""asyncpg connection pool + FastAPI dependency."""
from __future__ import annotations

import asyncpg
from fastapi import Request


async def create_pool(database_url: str) -> asyncpg.Pool:
    # asyncpg uses postgresql:// not postgresql+asyncpg://
    url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.create_pool(url, min_size=2, max_size=10)


async def get_db(request: Request):
    """FastAPI dependency — yields a connection from the pool."""
    async with request.app.state.db.acquire() as conn:
        yield conn
