import pytest
from pathlib import Path
from modelmesh.registry.model_registry import ModelRegistry, ModelEntry

FIXTURE_YAML = Path("config/models.yaml")


def test_loads_models():
    registry = ModelRegistry(FIXTURE_YAML)
    assert "llama3.2:3b" in registry.list_models()
    assert "gpt-4o" in registry.list_models()


def test_get_model_entry():
    registry = ModelRegistry(FIXTURE_YAML)
    entry = registry.get("llama3.2:3b")
    assert entry is not None
    assert entry.provider == "ollama"
    assert entry.context_window == 8192


def test_get_unknown_model_returns_none():
    registry = ModelRegistry(FIXTURE_YAML)
    assert registry.get("does-not-exist") is None


def test_default_chat_model():
    registry = ModelRegistry(FIXTURE_YAML)
    assert registry.default_chat_model == "llama3.2:3b"
