import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from modelmesh.router.rule_router import RuleRouter
from modelmesh.providers.base import ChatRequest, Message
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
_router: RuleRouter | None = None


def get_router() -> RuleRouter:
    return _router

def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    rule_router = get_router()
    try:
        provider, resolved_model = await rule_router.resolve(req.model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    chat_req = ChatRequest(
        model=resolved_model,
        messages=[Message(role=m.role, content=m.content) for m in req.messages],
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=req.stream,
    )

    logger.info("chat_request", extra={"model": resolved_model, "messages": len(req.messages)})

    if req.stream:
        return StreamingResponse(
            _stream_response(provider, chat_req, resolved_model),
            media_type="text/event-stream",
        )

    resp = await provider.chat(chat_req)
    return {
        "id": resp.id,
        "object": "chat.completion",
        "model": resp.model,
        "choices": resp.choices,
        "usage": resp.usage,
    }


async def _stream_response(provider, request: ChatRequest, model: str):
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
    yield f"data: {json.dumps({'id': resp_id, 'model': model, 'choices': [{'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
    async for token in provider.stream_chat(request):
        chunk = {"id": resp_id, "model": model, "choices": [{"delta": {"content": token}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"
    yield f"data: {json.dumps({'id': resp_id, 'model': model, 'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"
