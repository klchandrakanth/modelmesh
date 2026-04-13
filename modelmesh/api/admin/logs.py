"""GET /admin/logs — recent request log entries."""
from fastapi import APIRouter, Depends, Query
from modelmesh.api.admin.auth import require_jwt
from modelmesh.observability.request_log import get_request_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/logs", dependencies=[Depends(require_jwt)])
async def admin_logs(
    limit: int = Query(default=100, ge=1, le=500),
    model: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    entries = get_request_log().recent(limit=limit * 5)  # over-fetch then filter

    if model:
        entries = [e for e in entries if e.model == model]
    if provider:
        entries = [e for e in entries if e.provider == provider]
    if status:
        entries = [e for e in entries if e.status == status]

    entries = entries[:limit]

    return {
        "count": len(entries),
        "entries": [
            {
                "id": e.id,
                "timestamp": e.timestamp,
                "model": e.model,
                "provider": e.provider,
                "status": e.status,
                "latency_ms": e.latency_ms,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "cost_usd": e.cost_usd,
                "request_preview": e.request_preview,
            }
            for e in entries
        ],
    }
