import pytest
from modelmesh.observability.metrics import (
    record_request,
    observe_latency,
    record_tokens,
    record_cost,
    get_metrics_output,
)


def test_record_request_does_not_raise():
    record_request(provider="openai", model="gpt-4o", status="success")
    record_request(provider="ollama", model="llama3.2:3b", status="error")


def test_observe_latency_does_not_raise():
    observe_latency(provider="anthropic", model="claude-haiku-4-5", seconds=0.42)


def test_record_tokens_does_not_raise():
    record_tokens(
        provider="openai", model="gpt-4o", prompt_tokens=100, completion_tokens=50
    )


def test_record_cost_does_not_raise():
    record_cost(provider="openai", model="gpt-4o", cost_usd=0.005)


def test_get_metrics_output_returns_bytes_and_content_type():
    output, content_type = get_metrics_output()
    assert isinstance(output, bytes)
    assert "text/plain" in content_type


def test_metrics_output_contains_expected_metric_names():
    # Trigger some metrics so they appear in output
    record_request(provider="test-provider", model="test-model", status="success")
    output, _ = get_metrics_output()
    text = output.decode()
    assert "llm_requests_total" in text
    assert "llm_latency_seconds" in text
    assert "llm_tokens_total" in text
    assert "llm_cost_usd_total" in text
