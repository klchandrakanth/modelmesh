from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MODELMESH_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    models_config_path: Path = Path("config/models.yaml")
    routing_config_path: Path = Path("config/routing.yaml")

    ollama_base_url: str = "http://localhost:11434"

    # Provider API keys — loaded directly (no MODELMESH_ prefix)
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    huggingface_api_key: str | None = Field(default=None, validation_alias="HUGGINGFACE_API_KEY")

    # Bootstrap admin key
    gateway_admin_key: str = "dev-admin-key"

    # Auth
    keys_config_path: Path = Path("config/keys.yaml")
    enable_auth: bool = False  # Set True to require X-API-Key on all requests

    # Redis cache
    redis_url: str = "redis://localhost:6379"
    enable_cache: bool = False  # Set True to enable Redis prompt caching
    cache_ttl: int = 3600  # seconds

    # Observability
    enable_metrics: bool = True  # Prometheus /metrics endpoint

    # Semantic routing
    enable_semantic_routing: bool = False  # Requires sentence-transformers extra

    database_url: str = Field(
        default="postgresql+asyncpg://modelmesh:devpassword@localhost/modelmesh",
        validation_alias="DATABASE_URL",
    )

settings = Settings()
