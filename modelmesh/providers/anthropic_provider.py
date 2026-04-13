from typing import AsyncIterator
import anthropic
from .base import BaseProvider, ChatRequest, ChatResponse, EmbeddingRequest, EmbeddingResponse


class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        # Separate system message from conversation messages
        system = None
        messages = []
        for m in request.messages:
            if m.role == "system":
                system = m.content
            else:
                messages.append({"role": m.role, "content": m.content})

        kwargs = dict(
            model=request.model,
            messages=messages,
            max_tokens=request.max_tokens or 4096,
            temperature=request.temperature,
        )
        if system:
            kwargs["system"] = system

        resp = await self._client.messages.create(**kwargs)
        content = resp.content[0].text if resp.content else ""
        return ChatResponse(
            model=resp.model,
            content=content,
            prompt_tokens=resp.usage.input_tokens,
            completion_tokens=resp.usage.output_tokens,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        system = None
        messages = []
        for m in request.messages:
            if m.role == "system":
                system = m.content
            else:
                messages.append({"role": m.role, "content": m.content})

        kwargs = dict(
            model=request.model,
            messages=messages,
            max_tokens=request.max_tokens or 4096,
            temperature=request.temperature,
        )
        if system:
            kwargs["system"] = system

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except (anthropic.AuthenticationError, anthropic.APIConnectionError):
            return False

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.models.list()
            return [m.id for m in resp.data]
        except Exception:
            # Return known models as fallback if API doesn't support listing
            return ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"]
