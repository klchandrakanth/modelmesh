from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator
import uuid


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    tools: list | None = None  # OpenAI-compatible tool definitions for agent mode


@dataclass
class ChatResponse:
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list | None = None  # populated when model calls tools
    id: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")

    @property
    def choices(self) -> list[dict]:
        message: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return [{
            "index": 0,
            "message": message,
            "finish_reason": "tool_calls" if self.tool_calls else "stop",
        }]

    @property
    def usage(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }


@dataclass
class EmbeddingRequest:
    model: str
    input: str | list[str]


@dataclass
class EmbeddingResponse:
    model: str
    embeddings: list[list[float]]
    prompt_tokens: int = 0


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]: ...

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...
