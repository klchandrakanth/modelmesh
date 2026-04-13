import pytest
from unittest.mock import AsyncMock
from modelmesh.router.rule_router import RuleRouter
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.providers.base import BaseProvider
from pathlib import Path


@pytest.fixture
def registry():
    return ModelRegistry(Path("config/models.yaml"))


@pytest.fixture
def mock_ollama():
    p = AsyncMock(spec=BaseProvider)
    p.health_check.return_value = True
    return p


@pytest.fixture
def mock_openai():
    p = AsyncMock(spec=BaseProvider)
    p.health_check.return_value = True
    return p


@pytest.fixture
def router(registry, mock_ollama, mock_openai):
    return RuleRouter(
        registry=registry,
        providers={"ollama": mock_ollama, "openai": mock_openai},
        default_local_first=True,
    )


@pytest.mark.asyncio
async def test_explicit_model_resolves_to_provider(router, mock_ollama):
    provider, model = await router.resolve("llama3.2:3b")
    assert provider is mock_ollama
    assert model == "llama3.2:3b"


@pytest.mark.asyncio
async def test_explicit_openai_model(router, mock_openai):
    provider, _ = await router.resolve("gpt-4o")
    assert provider is mock_openai


@pytest.mark.asyncio
async def test_auto_resolves_to_default(router, mock_ollama):
    provider, _ = await router.resolve("auto")
    assert provider is mock_ollama   # local_first=True, ollama healthy


@pytest.mark.asyncio
async def test_auto_falls_back_when_ollama_down(registry, mock_ollama):
    mock_anthropic = AsyncMock(spec=BaseProvider)
    mock_anthropic.health_check.return_value = True
    mock_ollama.health_check.return_value = False
    local_router = RuleRouter(
        registry=registry,
        providers={"ollama": mock_ollama, "anthropic": mock_anthropic},
        default_local_first=True,
    )
    provider, _ = await local_router.resolve("auto")
    assert provider is mock_anthropic


@pytest.mark.asyncio
async def test_unknown_model_raises(router):
    with pytest.raises(ValueError, match="Unknown model"):
        await router.resolve("does-not-exist")
