"""Semantic (intent-based) router for ModelMesh.

When model="auto", classifies the user message into an intent bucket and
maps it to the best available model. Falls back gracefully to RuleRouter
if sentence-transformers is not installed.

Intent → model mapping is defined in INTENT_MODEL_MAP and can be overridden
via routing.yaml (future).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from modelmesh.providers.base import BaseProvider

if TYPE_CHECKING:
    from modelmesh.router.rule_router import RuleRouter

logger = logging.getLogger(__name__)

# Prototype examples used to compute per-intent centroids
_INTENT_EXAMPLES: dict[str, list[str]] = {
    "code": [
        "write a function",
        "debug this code",
        "fix this bug",
        "implement this class",
        "refactor this method",
        "write unit tests",
        "explain this algorithm",
    ],
    "summarize": [
        "summarize this text",
        "give me a summary",
        "tldr",
        "what are the main points",
        "condense this",
        "bullet points of key ideas",
    ],
    "creative": [
        "write a story",
        "compose a poem",
        "be creative",
        "imagine a scenario",
        "write a song",
        "create a narrative",
    ],
    "factual": [
        "what is",
        "explain how",
        "when did",
        "define",
        "what does mean",
        "how does work",
    ],
    "long_form": [
        "write a detailed essay",
        "comprehensive analysis",
        "in depth explanation",
        "write a report",
        "thorough review",
    ],
    "fast": [
        "quick answer",
        "briefly",
        "one sentence",
        "yes or no",
        "short response",
        "in two words",
    ],
}

# Intent → (primary model, fallback model)
# Primary is tried first; if unavailable, fallback is used; then rule_router auto
INTENT_MODEL_MAP: dict[str, dict[str, str]] = {
    "code": {"primary": "llama3.2:3b", "fallback": "claude-haiku-4-5"},
    "summarize": {"primary": "llama3.2:3b", "fallback": "claude-haiku-4-5"},
    "creative": {"primary": "claude-sonnet-4-5", "fallback": "gpt-4o"},
    "factual": {"primary": "llama3.2:3b", "fallback": "claude-haiku-4-5"},
    "long_form": {"primary": "claude-sonnet-4-5", "fallback": "gpt-4o"},
    "fast": {"primary": "llama3.2:3b", "fallback": "claude-haiku-4-5"},
}


class IntentClassifier:
    """Nearest-centroid classifier using sentence-transformers embeddings."""

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            import numpy as np  # type: ignore
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for semantic routing. "
                "Install with: pip install 'modelmesh[semantic]'"
            ) from e

        self._np = np
        logger.info("Loading intent classifier model: %s", self.MODEL_NAME)
        self._model = SentenceTransformer(self.MODEL_NAME)
        self._centroids = self._compute_centroids()
        logger.info("Intent classifier ready (%d intents)", len(self._centroids))

    def _compute_centroids(self) -> dict[str, "np.ndarray"]:
        centroids = {}
        for intent, examples in _INTENT_EXAMPLES.items():
            embeddings = self._model.encode(examples, show_progress_bar=False)
            centroids[intent] = embeddings.mean(axis=0)
        return centroids

    def _cosine_similarity(self, a: "np.ndarray", b: "np.ndarray") -> float:
        denom = self._np.linalg.norm(a) * self._np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(self._np.dot(a, b) / denom)

    def classify(self, text: str) -> str:
        """Return the most likely intent for the given text."""
        emb = self._model.encode([text], show_progress_bar=False)[0]
        best_intent = max(
            self._centroids,
            key=lambda k: self._cosine_similarity(emb, self._centroids[k]),
        )
        return best_intent


class SemanticRouter:
    """Wraps RuleRouter, adding intent-based model selection for model='auto'."""

    def __init__(self, rule_router: "RuleRouter", classifier: IntentClassifier) -> None:
        self._rule_router = rule_router
        self._classifier = classifier

    async def resolve(
        self, model_name: str, messages: list | None = None
    ) -> tuple[BaseProvider, str]:
        # Explicit model — delegate directly, no classification needed
        if model_name not in ("auto", None, ""):
            return await self._rule_router.resolve(model_name)

        # Extract last user message for classification
        last_user_msg = ""
        if messages:
            for m in reversed(messages):
                role = m.role if hasattr(m, "role") else m.get("role", "")
                if role == "user":
                    last_user_msg = m.content if hasattr(m, "content") else m.get("content", "")
                    break

        if not last_user_msg:
            return await self._rule_router.resolve("auto")

        intent = self._classifier.classify(last_user_msg)
        logger.debug("Classified intent: %s for message: %.80s", intent, last_user_msg)

        intent_config = INTENT_MODEL_MAP.get(intent, {})

        # Try primary model
        primary = intent_config.get("primary")
        if primary:
            try:
                return await self._rule_router.resolve(primary)
            except (ValueError, RuntimeError) as e:
                logger.debug("Primary model %r unavailable: %s", primary, e)

        # Try fallback model
        fallback = intent_config.get("fallback")
        if fallback:
            try:
                return await self._rule_router.resolve(fallback)
            except (ValueError, RuntimeError) as e:
                logger.debug("Fallback model %r unavailable: %s", fallback, e)

        # Final fallback to rule router's auto resolution
        return await self._rule_router.resolve("auto")
