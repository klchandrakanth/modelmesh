from modelmesh.registry.model_registry import ModelRegistry
from modelmesh.providers.base import BaseProvider


class RuleRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        providers: dict[str, BaseProvider],
        default_local_first: bool = True,
    ):
        self._registry = registry
        self._providers = providers
        self._local_first = default_local_first

    async def resolve(self, model_name: str) -> tuple[BaseProvider, str]:
        """Return (provider, resolved_model_name)."""
        if model_name in ("auto", None, ""):
            return await self._resolve_auto()

        entry = self._registry.get(model_name)
        if entry is None:
            raise ValueError(f"Unknown model: {model_name!r}")

        provider = self._providers.get(entry.provider)
        if provider is None:
            raise ValueError(f"No provider registered for: {entry.provider!r}")

        return provider, model_name

    async def _resolve_auto(self) -> tuple[BaseProvider, str]:
        """Local-first: try Ollama default, then fallback."""
        if self._local_first and "ollama" in self._providers:
            ollama = self._providers["ollama"]
            if await ollama.health_check():
                default = self._registry.default_chat_model
                entry = self._registry.get(default)
                if entry and entry.provider == "ollama":
                    return ollama, default
                # default isn't on ollama — pick first ollama model from registry
                for name in self._registry.list_models():
                    e = self._registry.get(name)
                    if e and e.provider == "ollama":
                        return ollama, name

        # fallback to first available cloud provider
        fallback_name = self._registry.fallback_model
        entry = self._registry.get(fallback_name)
        if entry:
            provider = self._providers.get(entry.provider)
            if provider:
                return provider, fallback_name

        raise RuntimeError("No available providers")
