import pytest
import respx
import httpx
from modelmesh.providers.ollama import OllamaProvider
from modelmesh.providers.base import ChatRequest, Message


@pytest.fixture
def provider():
    return OllamaProvider(base_url="http://localhost:11434")


@respx.mock
@pytest.mark.asyncio
async def test_chat_returns_response(provider):
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hello!"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        })
    )
    req = ChatRequest(model="llama3", messages=[Message(role="user", content="Hi")])
    resp = await provider.chat(req)
    assert resp.content == "Hello!"
    assert resp.model == "llama3"
    assert resp.prompt_tokens == 10


@respx.mock
@pytest.mark.asyncio
async def test_health_check_true_when_reachable(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert await provider.health_check() is True


@respx.mock
@pytest.mark.asyncio
async def test_health_check_false_when_unreachable(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await provider.health_check() is False


@respx.mock
@pytest.mark.asyncio
async def test_list_models(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={
            "models": [{"name": "llama3"}, {"name": "deepseek-coder"}]
        })
    )
    models = await provider.list_models()
    assert "llama3" in models
