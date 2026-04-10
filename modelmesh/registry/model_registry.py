from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class ModelEntry:
    name: str
    provider: str
    context_window: int = 4096
    cost_per_1k_tokens: float = 0.0


class ModelRegistry:
    def __init__(self, config_path: Path):
        self._models: dict[str, ModelEntry] = {}
        self._defaults: dict[str, str] = {}
        self._load(config_path)

    def _load(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text())
        for name, attrs in data.get("models", {}).items():
            self._models[name] = ModelEntry(
                name=name,
                provider=attrs["provider"],
                context_window=attrs.get("context_window", 4096),
                cost_per_1k_tokens=attrs.get("cost_per_1k_tokens", 0.0),
            )
        self._defaults = data.get("defaults", {})

    def get(self, model_name: str) -> ModelEntry | None:
        return self._models.get(model_name)

    def list_models(self) -> list[str]:
        return list(self._models.keys())

    @property
    def default_chat_model(self) -> str:
        return self._defaults.get("chat", next(iter(self._models)))

    @property
    def fallback_model(self) -> str:
        return self._defaults.get("fallback", self.default_chat_model)
