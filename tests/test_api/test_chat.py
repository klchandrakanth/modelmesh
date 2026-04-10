import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from modelmesh.main import create_app
from modelmesh.providers.base import ChatResponse


@pytest.fixture
def mock_router(mock_chat_response):
    router = AsyncMock()
    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=mock_chat_response)
    router.resolve = AsyncMock(return_value=(mock_provider, "llama3"))
    return router


@pytest.fixture
def client(mock_router):
    with patch("modelmesh.api.v1.chat._router", mock_router):
        with TestClient(create_app()) as c:
            yield c


def test_chat_completions_returns_200(client, mock_chat_response):
    resp = client.post("/v1/chat/completions", json={
        "model": "llama3",
        "messages": [{"role": "user", "content": "Hello"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Test response"
    assert data["model"] == "llama3"
    assert "usage" in data


def test_chat_completions_unknown_model_returns_404():
    mock_router = AsyncMock()
    mock_router.resolve = AsyncMock(side_effect=ValueError("Unknown model: 'bad'"))
    with patch("modelmesh.api.v1.chat._router", mock_router):
        with TestClient(create_app()) as c:
            resp = c.post("/v1/chat/completions", json={
                "model": "bad",
                "messages": [{"role": "user", "content": "Hello"}],
            })
            assert resp.status_code == 404
