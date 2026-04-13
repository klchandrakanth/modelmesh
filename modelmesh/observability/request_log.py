"""In-memory request log ring buffer for ModelMesh admin UI.

Stores the last MAX_ENTRIES requests in memory.
Each entry captures enough detail for the Logs and Dashboard pages.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


MAX_ENTRIES = 500


@dataclass
class RequestLogEntry:
    id: str
    timestamp: float          # Unix epoch seconds
    model: str
    provider: str
    status: str               # success | error | stream
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    request_preview: str      # first 120 chars of last user message


class RequestLog:
    """Thread-safe-ish ring buffer (asyncio single-threaded, no lock needed)."""

    def __init__(self, maxlen: int = MAX_ENTRIES) -> None:
        self._entries: deque[RequestLogEntry] = deque(maxlen=maxlen)

    def append(
        self,
        *,
        model: str,
        provider: str,
        status: str,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
        request_preview: str = "",
    ) -> None:
        self._entries.append(
            RequestLogEntry(
                id=uuid.uuid4().hex[:12],
                timestamp=time.time(),
                model=model,
                provider=provider,
                status=status,
                latency_ms=round(latency_ms, 1),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=round(cost_usd, 6),
                request_preview=request_preview[:120],
            )
        )

    def recent(self, limit: int = 100) -> list[RequestLogEntry]:
        entries = list(self._entries)
        return list(reversed(entries))[:limit]

    def metrics_summary(self) -> dict:
        """Aggregate stats for the Dashboard page."""
        entries = list(self._entries)
        if not entries:
            return {
                "total_requests": 0,
                "success_rate": 1.0,
                "avg_latency_ms": 0.0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "requests_by_model": {},
                "requests_by_provider": {},
                "requests_by_status": {},
            }

        total = len(entries)
        successes = sum(1 for e in entries if e.status == "success")
        total_tokens = sum(e.prompt_tokens + e.completion_tokens for e in entries)
        total_cost = sum(e.cost_usd for e in entries)
        avg_latency = sum(e.latency_ms for e in entries) / total

        by_model: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for e in entries:
            by_model[e.model] = by_model.get(e.model, 0) + 1
            by_provider[e.provider] = by_provider.get(e.provider, 0) + 1
            by_status[e.status] = by_status.get(e.status, 0) + 1

        return {
            "total_requests": total,
            "success_rate": round(successes / total, 4),
            "avg_latency_ms": round(avg_latency, 1),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "requests_by_model": dict(
                sorted(by_model.items(), key=lambda x: x[1], reverse=True)
            ),
            "requests_by_provider": by_provider,
            "requests_by_status": by_status,
        }


# Module-level singleton wired by main.py
_log: Optional[RequestLog] = None


def get_request_log() -> RequestLog:
    global _log
    if _log is None:
        _log = RequestLog()
    return _log


def set_request_log(log: RequestLog) -> None:
    global _log
    _log = log
