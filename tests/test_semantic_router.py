"""Tests for SemanticRouter.

We mock out IntentClassifier so these tests don't require sentence-transformers
to be installed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from modelmesh.router.semantic_router import SemanticRouter, INTENT_MODEL_MAP
from modelmesh.providers.base import BaseProvider


def _make_classifier(intent: str) -> MagicMock:
    clf = MagicMock()
    clf.classify.return_value = intent
    return clf


def _make_rule_router(resolved_model: str = "llama3.2:3b") -> MagicMock:
    mock_provider = AsyncMock(spec=BaseProvider)
    rr = MagicMock()
    rr.resolve = AsyncMock(return_value=(mock_provider, resolved_model))
    return rr, mock_provider


@pytest.mark.asyncio
async def test_explicit_model_bypasses_classifier():
    clf = _make_classifier("code")
    rr, mock_provider = _make_rule_router("gpt-4o")
    router = SemanticRouter(rule_router=rr, classifier=clf)

    provider, model = await router.resolve("gpt-4o", messages=[])

    clf.classify.assert_not_called()
    assert model == "gpt-4o"


@pytest.mark.asyncio
async def test_auto_classifies_and_resolves_primary():
    clf = _make_classifier("code")
    rr, mock_provider = _make_rule_router("llama3.2:3b")
    router = SemanticRouter(rule_router=rr, classifier=clf)

    messages = [{"role": "user", "content": "write a function to sort a list"}]
    provider, model = await router.resolve("auto", messages=messages)

    clf.classify.assert_called_once()
    # Should have tried the primary model for "code" intent
    primary = INTENT_MODEL_MAP["code"]["primary"]
    rr.resolve.assert_called_with(primary)


@pytest.mark.asyncio
async def test_falls_back_when_primary_unavailable():
    clf = _make_classifier("creative")

    # primary raises ValueError, fallback succeeds
    mock_provider = AsyncMock(spec=BaseProvider)
    call_count = {"n": 0}

    async def mock_resolve(model_name):
        call_count["n"] += 1
        primary = INTENT_MODEL_MAP["creative"]["primary"]
        fallback = INTENT_MODEL_MAP["creative"]["fallback"]
        if model_name == primary:
            raise ValueError(f"Unknown model: {model_name!r}")
        return mock_provider, model_name

    rr = MagicMock()
    rr.resolve = mock_resolve
    router = SemanticRouter(rule_router=rr, classifier=clf)

    messages = [{"role": "user", "content": "write me a poem about the sea"}]
    provider, model = await router.resolve("auto", messages=messages)

    fallback = INTENT_MODEL_MAP["creative"]["fallback"]
    assert model == fallback


@pytest.mark.asyncio
async def test_empty_messages_falls_back_to_auto():
    clf = _make_classifier("fast")
    rr, mock_provider = _make_rule_router("llama3.2:3b")
    router = SemanticRouter(rule_router=rr, classifier=clf)

    await router.resolve("auto", messages=[])

    clf.classify.assert_not_called()
    rr.resolve.assert_called_with("auto")


@pytest.mark.asyncio
async def test_uses_last_user_message_for_classification():
    clf = _make_classifier("summarize")
    rr, _ = _make_rule_router()
    router = SemanticRouter(rule_router=rr, classifier=clf)

    class Msg:
        def __init__(self, role, content):
            self.role = role
            self.content = content

    messages = [
        Msg("system", "You are a helper"),
        Msg("user", "Summarize this article"),
        Msg("assistant", "Sure!"),
        Msg("user", "Actually, give key bullet points"),
    ]
    await router.resolve("auto", messages=messages)
    clf.classify.assert_called_once_with("Actually, give key bullet points")
