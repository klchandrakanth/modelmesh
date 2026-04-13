"""HuggingFace Inference API provider for ModelMesh.

Uses HuggingFace's OpenAI-compatible Inference API:
  POST https://api-inference.huggingface.co/v1/chat/completions

Requires: HUGGINGFACE_API_KEY environment variable (HF access token).
"""
from __future__ import annotations

import json
import uuid

import httpx

from modelmesh.providers.base import (
    BaseProvider,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

_HF_BASE_URL = "https://api-inference.huggingface.co/v1"
_DEFAULT_MODEL = "meta-llama/Llama-3.2-3B-Instruct"


class HuggingFaceProvider(BaseProvider):
    """Provider backed by HuggingFace Serverless Inference API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = _HF_BASE_URL,
        default_model: str = _DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _model_name(self, request: ChatRequest) -> str:
        return request.model or self._default_model

    async def chat(self, request: ChatRequest) -> ChatResponse:
        model = self._model_name(request)
        payload: dict = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            built = client.build_request(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response = await client.send(built)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return ChatResponse(
            id=data.get("id", f"chatcmpl-{uuid.uuid4().hex[:8]}"),
            model=model,
            content=choice["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    async def stream_chat(self, request: ChatRequest):
        model = self._model_name(request)
        payload: dict = {
            "model": model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "temperature": request.temperature,
            "stream": True,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload_str = line[6:]
                    if payload_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload_str)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model = request.model or self._default_model
        payload = {"model": model, "input": request.input}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/embeddings",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        # HF returns {"data": [{"embedding": [...]}], ...}
        embeddings = [item["embedding"] for item in data.get("data", [])]
        usage = data.get("usage", {})
        return EmbeddingResponse(
            model=data.get("model", model),
            embeddings=embeddings,
            prompt_tokens=usage.get("prompt_tokens", 0),
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers=self._headers(),
                )
                return resp.status_code < 500
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        return [
            "meta-llama/Llama-3.2-3B-Instruct",
            "meta-llama/Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "HuggingFaceH4/zephyr-7b-beta",
        ]
