import inspect
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from modelmesh.auth.api_keys import require_api_key
from modelmesh.observability.metrics import (
    record_request,
    observe_latency,
    record_tokens,
    record_cost,
)
from modelmesh.observability.request_log import get_request_log
from modelmesh.providers.base import ChatRequest, Message
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.router.rule_router import RuleRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_router: Optional[RuleRouter] = None
_cache = None  # Optional[RedisCache] — typed loosely to avoid circular import
_registry: Optional[ModelRegistry] = None


def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


def get_router() -> RuleRouter:
    return _router


def set_cache(c) -> None:
    global _cache
    _cache = c


def set_registry(r: ModelRegistry) -> None:
    global _registry
    _registry = r


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


def _cost_for(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if _registry is None:
        return 0.0
    entry = _registry.get(model)
    if entry is None:
        return 0.0
    rate = entry.cost_per_1k_tokens
    return (prompt_tokens + completion_tokens) / 1000.0 * rate


@router.post("/v1/chat/completions", dependencies=[Depends(require_api_key)])
async def chat_completions(req: ChatCompletionRequest):
    rule_router = get_router()

    # Resolve provider — SemanticRouter.resolve accepts messages; RuleRouter ignores it
    try:
        sig = inspect.signature(rule_router.resolve)
        if "messages" in sig.parameters:
            provider, resolved_model = await rule_router.resolve(
                req.model, messages=req.messages
            )
        else:
            provider, resolved_model = await rule_router.resolve(req.model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    chat_req = ChatRequest(
        model=resolved_model,
        messages=[Message(role=m.role, content=m.content) for m in req.messages],
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=req.stream,
    )

    logger.info(
        "chat_request",
        extra={"model": resolved_model, "messages": len(req.messages)},
    )

    # Extract preview from last user message for the request log
    request_preview = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )
    provider_name = type(provider).__name__.lower().replace("provider", "")

    if req.stream:
        record_request(provider=provider_name, model=resolved_model, status="stream")
        get_request_log().append(
            model=resolved_model,
            provider=provider_name,
            status="stream",
            latency_ms=0,
            request_preview=request_preview,
        )
        return StreamingResponse(
            _stream_response(provider, chat_req, resolved_model, provider_name),
            media_type="text/event-stream",
        )

    # Check cache
    messages_payload = [
        {"role": m.role, "content": m.content} for m in req.messages
    ]
    if _cache is not None and _cache.is_available:
        cached = await _cache.get(resolved_model, messages_payload)
        if cached is not None:
            logger.debug("Cache hit for model=%s", resolved_model)
            return cached

    # Call provider + measure latency
    start = time.monotonic()
    try:
        resp = await provider.chat(chat_req)
        status = "success"
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        record_request(provider=provider_name, model=resolved_model, status="error")
        observe_latency(
            provider=provider_name,
            model=resolved_model,
            seconds=(time.monotonic() - start),
        )
        get_request_log().append(
            model=resolved_model,
            provider=provider_name,
            status="error",
            latency_ms=elapsed_ms,
            request_preview=request_preview,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    elapsed = time.monotonic() - start
    elapsed_ms = elapsed * 1000
    record_request(provider=provider_name, model=resolved_model, status=status)
    observe_latency(provider=provider_name, model=resolved_model, seconds=elapsed)

    usage = resp.usage or {}
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost = 0.0
    if prompt_tokens or completion_tokens:
        record_tokens(
            provider=provider_name,
            model=resolved_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        cost = _cost_for(resolved_model, prompt_tokens, completion_tokens)
        if cost:
            record_cost(provider=provider_name, model=resolved_model, cost_usd=cost)

    get_request_log().append(
        model=resolved_model,
        provider=provider_name,
        status=status,
        latency_ms=elapsed_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost,
        request_preview=request_preview,
    )

    result = {
        "id": resp.id,
        "object": "chat.completion",
        "model": resp.model,
        "choices": resp.choices,
        "usage": resp.usage,
    }

    # Store in cache
    if _cache is not None and _cache.is_available:
        await _cache.set(resolved_model, messages_payload, result)

    return result


async def _stream_response(
    provider, request: ChatRequest, model: str, provider_name: str
):
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    start_chunk = {
        "id": resp_id,
        "model": model,
        "choices": [{"delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(start_chunk)}\n\n"
    token_count = 0
    async for token in provider.stream_chat(request):
        token_count += 1
        chunk = {
            "id": resp_id,
            "model": model,
            "choices": [{"delta": {"content": token}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
    end_chunk = {
        "id": resp_id,
        "model": model,
        "choices": [{"delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(end_chunk)}\n\n"
    yield "data: [DONE]\n\n"
    record_tokens(
        provider=provider_name,
        model=model,
        prompt_tokens=0,
        completion_tokens=token_count,
    )
