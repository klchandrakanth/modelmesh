import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modelmesh.providers.openai_provider import OpenAIProvider
from modelmesh.providers.base import ChatRequest, Message


@pytest.fixture
def provider():
    return OpenAIProvider(api_key="sk-test")


@pytest.mark.asyncio
async def test_chat_returns_response(provider):
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    with patch.object(provider._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
        req = ChatRequest(model="gpt-4o", messages=[Message(role="user", content="Hi")])
        resp = await provider.chat(req)
        assert resp.content == "Hello!"
        assert resp.model == "gpt-4o"


@pytest.mark.asyncio
async def test_health_check_true(provider):
    with patch.object(provider._client.models, "list", new=AsyncMock(return_value=MagicMock())):
        assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_health_check_false_on_auth_error(provider):
    from openai import AuthenticationError
    import httpx
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.headers = {}
    with patch.object(provider._client.models, "list",
                      new=AsyncMock(side_effect=AuthenticationError("bad key", response=mock_resp, body=None))):
        assert await provider.health_check() is False
