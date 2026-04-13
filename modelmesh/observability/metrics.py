"""Prometheus metrics for ModelMesh.

All metrics are registered on a module-level CollectorRegistry so tests
can import this module without polluting the default REGISTRY.
"""
from prometheus_client import (
    Counter,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

registry = CollectorRegistry(auto_describe=False)

llm_requests_total = Counter(
    "llm_requests_total",
    "Total number of LLM requests",
    ["provider", "model", "status"],
    registry=registry,
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM request latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=registry,
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens processed",
    ["provider", "model", "type"],  # type: prompt | completion
    registry=registry,
)

llm_cost_usd_total = Counter(
    "llm_cost_usd_total",
    "Estimated total cost in USD",
    ["provider", "model"],
    registry=registry,
)


def record_request(provider: str, model: str, status: str = "success") -> None:
    llm_requests_total.labels(provider=provider, model=model, status=status).inc()


def observe_latency(provider: str, model: str, seconds: float) -> None:
    llm_latency_seconds.labels(provider=provider, model=model).observe(seconds)


def record_tokens(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> None:
    llm_tokens_total.labels(provider=provider, model=model, type="prompt").inc(
        prompt_tokens
    )
    llm_tokens_total.labels(provider=provider, model=model, type="completion").inc(
        completion_tokens
    )


def record_cost(provider: str, model: str, cost_usd: float) -> None:
    llm_cost_usd_total.labels(provider=provider, model=model).inc(cost_usd)


def get_metrics_output() -> tuple[bytes, str]:
    """Return (metrics_bytes, content_type) for the /metrics endpoint."""
    return generate_latest(registry), CONTENT_TYPE_LATEST
