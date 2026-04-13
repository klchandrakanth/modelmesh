"""Admin model management — GET, POST, PATCH, DELETE /admin/models"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from modelmesh.api.admin.auth import require_jwt
from modelmesh.db.connection import get_db
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.router.rule_router import RuleRouter

router = APIRouter(prefix="/admin", tags=["admin"])

_registry: Optional[ModelRegistry] = None
_router: Optional[RuleRouter] = None


def set_registry(r: ModelRegistry) -> None:
    global _registry
    _registry = r


def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


def _get_registry() -> ModelRegistry:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return _registry


@router.get("/models", dependencies=[Depends(require_jwt)])
async def admin_models():
    registry = _get_registry()
    models = []
    for name in registry.list_all_models():
        entry = registry.get(name)
        if entry is None:
            continue
        provider_healthy = None
        if _router and entry.provider in _router.providers:
            try:
                provider_healthy = await _router.providers[entry.provider].health_check()
            except Exception:
                provider_healthy = False
        models.append({
            "name": name,
            "provider": entry.provider,
            "context_window": entry.context_window,
            "cost_per_1k_tokens": entry.cost_per_1k_tokens,
            "is_default": name == registry.default_chat_model,
            "is_fallback": name == registry.fallback_model,
            "provider_healthy": provider_healthy,
            "enabled": entry.enabled,
        })
    return {"models": models}


class ModelCreateRequest(BaseModel):
    name: str
    provider: str
    context_window: int = 4096
    cost_per_1k: float = 0.0
    is_default: bool = False
    is_fallback: bool = False


@router.post("/models", dependencies=[Depends(require_jwt)], status_code=201)
async def create_model(body: ModelCreateRequest, db=Depends(get_db)):
    registry = _get_registry()
    await registry.add_model(
        db, body.name, body.provider, body.context_window,
        body.cost_per_1k, body.is_default, body.is_fallback,
    )
    return {"name": body.name, "status": "created"}


class ModelUpdateRequest(BaseModel):
    provider: Optional[str] = None
    context_window: Optional[int] = None
    cost_per_1k: Optional[float] = None
    is_default: Optional[bool] = None
    is_fallback: Optional[bool] = None
    enabled: Optional[bool] = None


@router.patch("/models/{name}", dependencies=[Depends(require_jwt)])
async def update_model(name: str, body: ModelUpdateRequest, db=Depends(get_db)):
    registry = _get_registry()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    await registry.update_model(db, name, fields)
    return {"name": name, "status": "updated"}


@router.delete("/models/{name}", dependencies=[Depends(require_jwt)])
async def delete_model(name: str, db=Depends(get_db)):
    registry = _get_registry()
    await registry.delete_model(db, name)
    return {"name": name, "status": "deleted"}
