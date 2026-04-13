"""GET /admin/models — list models from the registry with provider health."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from modelmesh.api.admin.auth import require_jwt
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.router.rule_router import RuleRouter

router = APIRouter(prefix="/admin", tags=["admin"])

_registry: ModelRegistry | None = None
_router: RuleRouter | None = None


def set_registry(r: ModelRegistry) -> None:
    global _registry
    _registry = r


def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


@router.get("/models", dependencies=[Depends(require_jwt)])
async def admin_models():
    if _registry is None:
        return {"models": []}

    models = []
    for name in _registry.list_models():
        entry = _registry.get(name)
        if entry is None:
            continue
        provider_healthy = None
        if _router and entry.provider in _router._providers:
            try:
                provider_healthy = await _router._providers[entry.provider].health_check()
            except Exception:
                provider_healthy = False
        models.append(
            {
                "name": name,
                "provider": entry.provider,
                "context_window": entry.context_window,
                "cost_per_1k_tokens": entry.cost_per_1k_tokens,
                "is_default": name == _registry.default_chat_model,
                "is_fallback": name == _registry.fallback_model,
                "provider_healthy": provider_healthy,
            }
        )
    return {"models": models}
