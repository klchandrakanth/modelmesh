import json
import pytest
import respx
import httpx
from modelmesh.providers.huggingface_provider import HuggingFaceProvider, _HF_BASE_URL
from modelmesh.providers.base import ChatRequest, Message


@pytest.fixture
def provider():
    return HuggingFaceProvider(api_key="hf-test-token")


@respx.mock
@pytest.mark.asyncio
async def test_chat_returns_response(provider):
    respx.post(f"{_HF_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-hf-1",
                "model": "meta-llama/Llama-3.2-3B-Instruct",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "Hello from HF!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
            },
        )
    )

    req = ChatRequest(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=[Message(role="user", content="Hi")],
    )
    resp = await provider.chat(req)
    assert resp.choices[0]["message"]["content"] == "Hello from HF!"
    assert resp.usage["total_tokens"] == 9


@respx.mock
@pytest.mark.asyncio
async def test_chat_sends_auth_header(provider):
    route = respx.post(f"{_HF_BASE_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-hf-2",
                "model": "meta-llama/Llama-3.2-3B-Instruct",
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
                ],
                "usage": {},
            },
        )
    )

    req = ChatRequest(
        model="meta-llama/Llama-3.2-3B-Instruct",
        messages=[Message(role="user", content="test")],
    )
    await provider.chat(req)

    assert route.called
    sent_request = route.calls[0].request
    assert "Bearer hf-test-token" in sent_request.headers.get("authorization", "")


@respx.mock
@pytest.mark.asyncio
async def test_health_check_true_on_200(provider):
    respx.get(f"{_HF_BASE_URL}/models").mock(return_value=httpx.Response(200, json=[]))
    assert await provider.health_check() is True


@respx.mock
@pytest.mark.asyncio
async def test_health_check_false_on_connection_error(provider):
    respx.get(f"{_HF_BASE_URL}/models").mock(side_effect=httpx.ConnectError("no connection"))
    assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_list_models_returns_list(provider):
    models = await provider.list_models()
    assert len(models) > 0
    assert all(isinstance(m, str) for m in models)
