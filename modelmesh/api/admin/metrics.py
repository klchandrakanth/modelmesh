"""GET /admin/metrics — aggregated stats from the in-memory request log."""
from fastapi import APIRouter, Depends
from modelmesh.api.admin.auth import require_jwt
from modelmesh.observability.request_log import get_request_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", dependencies=[Depends(require_jwt)])
async def admin_metrics():
    return get_request_log().metrics_summary()
