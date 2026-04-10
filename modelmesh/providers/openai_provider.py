from typing import AsyncIterator
from openai import AsyncOpenAI, AuthenticationError, APIConnectionError
from .base import BaseProvider, ChatRequest, ChatResponse, EmbeddingRequest, EmbeddingResponse


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        kwargs = dict(model=request.model, messages=messages, temperature=request.temperature)
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        resp = await self._client.chat.completions.create(**kwargs)
        return ChatResponse(
            model=resp.model,
            content=resp.choices[0].message.content,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        stream = await self._client.chat.completions.create(
            model=request.model, messages=messages,
            temperature=request.temperature, stream=True,
        )
        async for chunk in stream:
            if content := chunk.choices[0].delta.content:
                yield content

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        inputs = request.input if isinstance(request.input, list) else [request.input]
        resp = await self._client.embeddings.create(model=request.model, input=inputs)
        return EmbeddingResponse(
            model=resp.model,
            embeddings=[d.embedding for d in resp.data],
            prompt_tokens=resp.usage.prompt_tokens,
        )

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except (AuthenticationError, APIConnectionError):
            return False

    async def list_models(self) -> list[str]:
        resp = await self._client.models.list()
        return [m.id for m in resp.data]
