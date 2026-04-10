from fastapi import APIRouter
from modelmesh.registry.model_registry import ModelRegistry

router = APIRouter()
_registry: ModelRegistry | None = None

def set_registry(r: ModelRegistry) -> None:
    global _registry
    _registry = r

@router.get("/v1/models")
async def list_models():
    models = _registry.list_models() if _registry else []
    return {
        "object": "list",
        "data": [{"id": m, "object": "model"} for m in models],
    }
