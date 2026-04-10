from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modelmesh.config.settings import settings
from modelmesh.observability.logging import configure_logging, get_logger
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.providers.ollama import OllamaProvider
from modelmesh.providers.openai_provider import OpenAIProvider
from modelmesh.router.rule_router import RuleRouter
from modelmesh.api.v1 import chat as chat_module
from modelmesh.api.v1 import models as models_module
from modelmesh.api.v1.chat import router as chat_router
from modelmesh.api.v1.models import router as models_router

logger = get_logger(__name__)


def _build_providers(s) -> dict:
    providers = {}
    providers["ollama"] = OllamaProvider(base_url=s.ollama_base_url)
    if s.openai_api_key:
        providers["openai"] = OpenAIProvider(api_key=s.openai_api_key)
    return providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    registry = ModelRegistry(settings.models_config_path)
    providers = _build_providers(settings)

    ollama_up = await providers["ollama"].health_check()
    logger.info("startup", extra={"ollama_available": ollama_up, "providers": list(providers.keys())})

    router = RuleRouter(registry=registry, providers=providers, default_local_first=True)

    chat_module.set_router(router)
    models_module.set_registry(registry)

    # Wire embeddings if the module exists (added in Task 12)
    try:
        from modelmesh.api.v1 import embeddings as embeddings_module
        embeddings_module.set_router(router)
    except ImportError:
        pass

    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="ModelMesh", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(models_router)

    # Include embeddings router if module exists
    try:
        from modelmesh.api.v1.embeddings import router as embeddings_router
        app.include_router(embeddings_router)
    except ImportError:
        pass

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("modelmesh.main:app", host=settings.host, port=settings.port, reload=True)
