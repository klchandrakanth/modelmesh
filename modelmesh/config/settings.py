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

settings = Settings()
