from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from modelmesh.config.settings import settings
from modelmesh.observability.logging import configure_logging, get_logger
from modelmesh.observability.metrics import get_metrics_output
from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.providers.ollama import OllamaProvider
from modelmesh.providers.openai_provider import OpenAIProvider
from modelmesh.providers.anthropic_provider import AnthropicProvider
from modelmesh.router.rule_router import RuleRouter
from modelmesh.auth.api_keys import ApiKeyManager, configure_auth
from modelmesh.observability.request_log import RequestLog, set_request_log
from modelmesh.api.v1 import chat as chat_module
from modelmesh.api.v1 import models as models_module
from modelmesh.api.v1.chat import router as chat_router
from modelmesh.api.v1.models import router as models_router
from modelmesh.api.admin import metrics as admin_metrics_module
from modelmesh.api.admin import logs as admin_logs_module
from modelmesh.api.admin import models as admin_models_module
from modelmesh.api.admin import health as admin_health_module
from modelmesh.api.admin import keys as admin_keys_module
from modelmesh.db.connection import create_pool
from modelmesh.db.schema import init_schema
from modelmesh.api.admin import auth_endpoints as admin_auth_module

logger = get_logger(__name__)


def _build_providers(s) -> dict:
    providers = {}
    providers["ollama"] = OllamaProvider(base_url=s.ollama_base_url)
    if s.openai_api_key:
        providers["openai"] = OpenAIProvider(api_key=s.openai_api_key)
    if s.anthropic_api_key:
        providers["anthropic"] = AnthropicProvider(api_key=s.anthropic_api_key)
    if s.huggingface_api_key:
        from modelmesh.providers.huggingface_provider import HuggingFaceProvider
        providers["huggingface"] = HuggingFaceProvider(api_key=s.huggingface_api_key)
    return providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)

    # Database
    db_pool = await create_pool(settings.database_url)
    await init_schema(db_pool, settings.models_config_path)
    app.state.db = db_pool

    # Registry + providers
    registry = ModelRegistry(settings.models_config_path)
    providers = _build_providers(settings)

    ollama_up = await providers["ollama"].health_check()
    logger.info(
        "startup",
        extra={
            "ollama_available": ollama_up,
            "providers": list(providers.keys()),
        },
    )

    # Base rule router
    rule_router = RuleRouter(registry=registry, providers=providers, default_local_first=True)

    # Semantic router (optional — requires sentence-transformers extra)
    active_router = rule_router
    if settings.enable_semantic_routing:
        try:
            from modelmesh.router.semantic_router import IntentClassifier, SemanticRouter
            classifier = IntentClassifier()
            active_router = SemanticRouter(rule_router=rule_router, classifier=classifier)
            logger.info("Semantic routing enabled")
        except ImportError:
            logger.warning(
                "enable_semantic_routing=True but sentence-transformers not installed; "
                "falling back to rule-based routing"
            )

    # Auth
    key_manager = ApiKeyManager(settings.keys_config_path)
    configure_auth(key_manager, enabled=settings.enable_auth)
    logger.info("auth", extra={"enabled": settings.enable_auth})

    # Redis cache (optional)
    cache = None
    if settings.enable_cache:
        from modelmesh.cache.redis_cache import RedisCache
        cache = RedisCache(url=settings.redis_url, ttl=settings.cache_ttl)
        await cache.connect()

    # Request log
    request_log = RequestLog()
    set_request_log(request_log)

    # Wire API modules
    chat_module.set_router(active_router)
    chat_module.set_cache(cache)
    models_module.set_registry(registry)

    # Wire admin modules
    admin_models_module.set_registry(registry)
    admin_models_module.set_router(rule_router)
    admin_health_module.set_router(rule_router)

    # Wire embeddings if available
    try:
        from modelmesh.api.v1 import embeddings as embeddings_module
        embeddings_module.set_router(rule_router)
    except ImportError:
        pass

    yield

    # Cleanup
    await db_pool.close()
    if cache is not None:
        await cache.close()
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="ModelMesh", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chat_router)
    app.include_router(models_router)

    # Admin routers
    app.include_router(admin_metrics_module.router)
    app.include_router(admin_logs_module.router)
    app.include_router(admin_models_module.router)
    app.include_router(admin_health_module.router)
    app.include_router(admin_keys_module.router)
    app.include_router(admin_auth_module.router)

    # Embeddings router (optional)
    try:
        from modelmesh.api.v1.embeddings import router as embeddings_router
        app.include_router(embeddings_router)
    except ImportError:
        pass

    # Prometheus metrics endpoint
    if settings.enable_metrics:
        @app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint():
            output, content_type = get_metrics_output()
            return Response(content=output, media_type=content_type)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("modelmesh.main:app", host=settings.host, port=settings.port, reload=True)
