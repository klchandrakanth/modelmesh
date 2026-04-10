from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from modelmesh.router.rule_router import RuleRouter
from modelmesh.providers.base import EmbeddingRequest

router = APIRouter()
_router: RuleRouter | None = None


def set_router(r: RuleRouter) -> None:
    global _router
    _router = r


class EmbeddingPayload(BaseModel):
    model: str
    input: str | list[str]


@router.post("/v1/embeddings")
async def create_embeddings(req: EmbeddingPayload):
    try:
        provider, resolved_model = await _router.resolve(req.model)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    emb_req = EmbeddingRequest(model=resolved_model, input=req.input)
    try:
        result = await provider.embeddings(emb_req)
    except NotImplementedError:
        raise HTTPException(status_code=422, detail=f"Model {resolved_model!r} does not support embeddings")

    return {
        "object": "list",
        "model": result.model,
        "data": [{"object": "embedding", "index": i, "embedding": emb}
                 for i, emb in enumerate(result.embeddings)],
        "usage": {"prompt_tokens": result.prompt_tokens, "total_tokens": result.prompt_tokens},
    }
