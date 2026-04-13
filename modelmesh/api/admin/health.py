"""GET /admin/health — per-provider health status."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from modelmesh.api.admin.auth import require_jwt
from modelmesh.router.rule_router import RuleRouter

router = APIRouter(prefix="/admin", tags=["admin"])

_router: RuleRouter | None = None


def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


@router.get("/health", dependencies=[Depends(require_jwt)])
async def admin_health():
    if _router is None:
        return {"providers": {}}

    results = {}
    for name, provider in _router._providers.items():
        try:
            healthy = await provider.health_check()
        except Exception as exc:
            healthy = False
        results[name] = {
            "healthy": healthy,
            "provider_class": type(provider).__name__,
        }

    return {"providers": results}
