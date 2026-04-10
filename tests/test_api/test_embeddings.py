"""Tests for the /v1/embeddings endpoint."""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from modelmesh.main import create_app
from modelmesh.providers.base import EmbeddingResponse


def test_embeddings_returns_200():
    """POST /v1/embeddings returns 200 with the expected embedding payload."""
    mock_router = AsyncMock()
    mock_provider = AsyncMock()
    mock_provider.embeddings = AsyncMock(return_value=EmbeddingResponse(
        model="text-embedding-ada-002",
        embeddings=[[0.1, 0.2, 0.3]],
        prompt_tokens=4,
    ))
    mock_router.resolve = AsyncMock(return_value=(mock_provider, "text-embedding-ada-002"))

    with patch("modelmesh.api.v1.embeddings._router", mock_router):
        with patch("modelmesh.main.chat_module.set_router"):
            with patch("modelmesh.api.v1.embeddings.set_router"):
                with TestClient(create_app()) as c:
                    resp = c.post("/v1/embeddings", json={
                        "model": "text-embedding-ada-002",
                        "input": "Hello world",
                    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert data["model"] == "text-embedding-ada-002"


def test_embeddings_unknown_model_returns_404():
    """POST /v1/embeddings returns 404 when the model cannot be resolved."""
    mock_router = AsyncMock()
    mock_router.resolve = AsyncMock(side_effect=ValueError("Unknown model: 'bad'"))

    with patch("modelmesh.api.v1.embeddings._router", mock_router):
        with patch("modelmesh.main.chat_module.set_router"):
            with patch("modelmesh.api.v1.embeddings.set_router"):
                with TestClient(create_app()) as c:
                    resp = c.post("/v1/embeddings", json={
                        "model": "bad",
                        "input": "hello",
                    })
    assert resp.status_code == 404
