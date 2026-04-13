"""GET /admin/metrics — aggregated stats from the in-memory request log."""
import time
from collections import defaultdict

from fastapi import APIRouter, Depends
from modelmesh.api.admin.auth import require_jwt
from modelmesh.observability.request_log import get_request_log

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", dependencies=[Depends(require_jwt)])
async def admin_metrics():
    return get_request_log().metrics_summary()


@router.get("/metrics/timeseries", dependencies=[Depends(require_jwt)])
async def admin_metrics_timeseries(window: str = "1h"):
    window_seconds = {"1h": 3600, "6h": 21600, "24h": 86400}.get(window, 3600)
    bucket_size = 300  # 5-minute buckets
    now = time.time()
    cutoff = now - window_seconds

    log = get_request_log()
    entries = [e for e in list(log._entries) if e.timestamp >= cutoff]

    buckets: dict[int, dict] = defaultdict(
        lambda: {"requests": 0, "errors": 0, "latency_sum": 0.0}
    )
    for e in entries:
        bucket_ts = int(e.timestamp // bucket_size) * bucket_size
        buckets[bucket_ts]["requests"] += 1
        if e.status == "error":
            buckets[bucket_ts]["errors"] += 1
        buckets[bucket_ts]["latency_sum"] += e.latency_ms

    result = [
        {
            "ts": ts,
            "requests": b["requests"],
            "errors": b["errors"],
            "avg_latency_ms": round(b["latency_sum"] / b["requests"], 1)
            if b["requests"] else 0.0,
        }
        for ts, b in sorted(buckets.items())
    ]

    actual_from = min((e.timestamp for e in entries), default=now)
    return {"window": window, "actual_from": actual_from, "buckets": result}
