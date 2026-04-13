# ModelMesh Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working OpenAI-compatible LLM gateway (ModelMesh) that routes requests to Ollama and OpenAI, deployable as a Docker container and on Kubernetes.

**Architecture:** Single FastAPI app serving `/v1/*` endpoints. A rule-based router resolves the model name to a provider via a YAML model registry. Ollama is auto-detected on startup (local-first default). The app is 12-factor: all secrets via env vars, config via mounted YAML files.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, httpx (async HTTP), PyYAML, uvicorn, pytest + pytest-asyncio, Docker, Kubernetes (manifests only — no Helm)

**Spec:** `docs/superpowers/specs/2026-04-03-modelmesh-design.md`

---

## File Map

```
modelmesh/
├── modelmesh/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Pydantic BaseSettings — env vars + YAML paths
│   ├── registry/
│   │   ├── __init__.py
│   │   └── model_registry.py      # Loads models.yaml → ModelEntry dataclass
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseProvider ABC
│   │   ├── ollama.py              # OllamaProvider (httpx)
│   │   └── openai_provider.py     # OpenAIProvider (openai SDK)
│   ├── router/
│   │   ├── __init__.py
│   │   └── rule_router.py         # Resolves model name → provider instance
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── chat.py            # POST /v1/chat/completions (stream + non-stream)
│   │       ├── embeddings.py      # POST /v1/embeddings
│   │       └── models.py          # GET /v1/models
│   └── observability/
│       ├── __init__.py
│       └── logging.py             # Structured JSON logger
├── tests/
│   ├── conftest.py                # Fixtures: mock providers, mock chat response
│   ├── test_config.py
│   ├── test_registry.py
│   ├── test_rule_router.py
│   ├── test_providers/
│   │   ├── test_base.py
│   │   ├── test_ollama.py
│   │   └── test_openai_provider.py
│   └── test_api/
│       ├── test_chat.py
│       └── test_models.py
├── config/
│   ├── models.yaml                # Model registry
│   └── routing.yaml               # Routing rules + intent labels
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secret.yaml
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `modelmesh/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`

- [ ] **Step 1: Create project root and pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "modelmesh"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "httpx>=0.27.0",
    "openai>=1.30.0",
    "anthropic>=0.28.0",
    "PyYAML>=6.0.1",
    "python-json-logger>=2.0.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-httpx>=0.30.0",
    "httpx>=0.27.0",
    "respx>=0.21.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p modelmesh/{config,registry,providers,router,api/v1,observability}
mkdir -p tests/{test_providers,test_api}
mkdir -p config k8s
touch modelmesh/__init__.py
touch modelmesh/{config,registry,providers,router,observability}/__init__.py
touch modelmesh/api/__init__.py modelmesh/api/v1/__init__.py
touch tests/__init__.py tests/test_providers/__init__.py tests/test_api/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git init
git add pyproject.toml modelmesh/ tests/
git commit -m "chore: scaffold modelmesh project"
```

---

## Task 2: Config & Settings

**Files:**
- Create: `modelmesh/config/settings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import os
from modelmesh.config.settings import Settings

def test_settings_defaults():
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.ollama_base_url == "http://localhost:11434"

def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("MODELMESH_PORT", "9000")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    s = Settings()
    assert s.port == 9000
    assert s.openai_api_key == "sk-test"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement settings**

Create `modelmesh/config/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    huggingface_api_key: str | None = None

    # Bootstrap admin key
    gateway_admin_key: str = "dev-admin-key"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/config/settings.py tests/test_config.py
git commit -m "feat: add Pydantic settings with env var support"
```

---

## Task 3: YAML Config Files

**Files:**
- Create: `config/models.yaml`
- Create: `config/routing.yaml`

- [ ] **Step 1: Create models.yaml**

```yaml
# config/models.yaml
models:
  gpt-4o:
    provider: openai
    context_window: 128000
    cost_per_1k_tokens: 0.005
  gpt-4o-mini:
    provider: openai
    context_window: 128000
    cost_per_1k_tokens: 0.00015
  llama3:
    provider: ollama
    context_window: 8192
    cost_per_1k_tokens: 0.0
  deepseek-coder:
    provider: ollama
    context_window: 16384
    cost_per_1k_tokens: 0.0
  phi3-mini:
    provider: ollama
    context_window: 4096
    cost_per_1k_tokens: 0.0

defaults:
  chat: llama3
  fallback: gpt-4o-mini
```

- [ ] **Step 2: Create routing.yaml**

```yaml
# config/routing.yaml
routing:
  local_first: true
  intent_map:
    code:
      primary: deepseek-coder
      fallback: gpt-4o
    summarize:
      primary: llama3
      fallback: gpt-4o-mini
    factual:
      primary: llama3
      fallback: gpt-4o-mini
    fast:
      primary: phi3-mini
      fallback: gpt-4o-mini

  intent_labels:
    code:
      - "Write a Python function"
      - "Fix this bug"
      - "Explain this code"
      - "Implement a REST endpoint"
      - "Debug this error"
    summarize:
      - "Summarize this document"
      - "Give me a TLDR"
      - "Condense this text"
    factual:
      - "What is the capital of France"
      - "Define machine learning"
      - "How does X work"
    fast:
      - "Yes or no"
      - "What time is it"
      - "Complete this sentence"
```

- [ ] **Step 3: Commit**

```bash
git add config/
git commit -m "chore: add models.yaml and routing.yaml config files"
```

---

## Task 4: Model Registry

**Files:**
- Create: `modelmesh/registry/model_registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_registry.py`:

```python
import pytest
from pathlib import Path
from modelmesh.registry.model_registry import ModelRegistry, ModelEntry

FIXTURE_YAML = Path("config/models.yaml")

def test_loads_models():
    registry = ModelRegistry(FIXTURE_YAML)
    assert "llama3" in registry.list_models()
    assert "gpt-4o" in registry.list_models()

def test_get_model_entry():
    registry = ModelRegistry(FIXTURE_YAML)
    entry = registry.get("llama3")
    assert entry is not None
    assert entry.provider == "ollama"
    assert entry.context_window == 8192

def test_get_unknown_model_returns_none():
    registry = ModelRegistry(FIXTURE_YAML)
    assert registry.get("does-not-exist") is None

def test_default_chat_model():
    registry = ModelRegistry(FIXTURE_YAML)
    assert registry.default_chat_model == "llama3"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_registry.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement model registry**

Create `modelmesh/registry/model_registry.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_registry.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/registry/ tests/test_registry.py
git commit -m "feat: add ModelRegistry with YAML loading"
```

---

## Task 5: Provider Base + Data Models

**Files:**
- Create: `modelmesh/providers/base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_providers/test_base.py`:

```python
import pytest
from modelmesh.providers.base import ChatRequest, ChatResponse, Message

def test_chat_request_roundtrip():
    req = ChatRequest(
        model="llama3",
        messages=[Message(role="user", content="Hello")]
    )
    assert req.model == "llama3"
    assert req.messages[0].role == "user"

def test_chat_response_has_required_fields():
    resp = ChatResponse(
        id="resp-1",
        model="llama3",
        content="Hi there",
        prompt_tokens=5,
        completion_tokens=3,
    )
    assert resp.choices[0]["message"]["content"] == "Hi there"
    assert resp.usage["total_tokens"] == 8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_providers/test_base.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement base models**

Create `modelmesh/providers/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator
import uuid


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False


@dataclass
class ChatResponse:
    model: str
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    id: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:8]}")

    @property
    def choices(self) -> list[dict]:
        return [{
            "index": 0,
            "message": {"role": "assistant", "content": self.content},
            "finish_reason": "stop",
        }]

    @property
    def usage(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }


@dataclass
class EmbeddingRequest:
    model: str
    input: str | list[str]


@dataclass
class EmbeddingResponse:
    model: str
    embeddings: list[list[float]]
    prompt_tokens: int = 0


class BaseProvider(ABC):
    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]: ...

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise NotImplementedError(f"{self.__class__.__name__} does not support embeddings")

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_providers/test_base.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/providers/base.py tests/test_providers/__init__.py tests/test_providers/test_base.py
git commit -m "feat: add BaseProvider ABC and data models"
```

---

## Task 6: OllamaProvider

**Files:**
- Create: `modelmesh/providers/ollama.py`
- Create: `tests/test_providers/test_ollama.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_providers/test_ollama.py`:

```python
import pytest
import respx
import httpx
import json
from modelmesh.providers.ollama import OllamaProvider
from modelmesh.providers.base import ChatRequest, Message


@pytest.fixture
def provider():
    return OllamaProvider(base_url="http://localhost:11434")


@respx.mock
@pytest.mark.asyncio
async def test_chat_returns_response(provider):
    respx.post("http://localhost:11434/api/chat").mock(
        return_value=httpx.Response(200, json={
            "model": "llama3",
            "message": {"role": "assistant", "content": "Hello!"},
            "prompt_eval_count": 10,
            "eval_count": 5,
        })
    )
    req = ChatRequest(model="llama3", messages=[Message(role="user", content="Hi")])
    resp = await provider.chat(req)
    assert resp.content == "Hello!"
    assert resp.model == "llama3"
    assert resp.prompt_tokens == 10


@respx.mock
@pytest.mark.asyncio
async def test_health_check_true_when_reachable(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={"models": []})
    )
    assert await provider.health_check() is True


@respx.mock
@pytest.mark.asyncio
async def test_health_check_false_when_unreachable(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await provider.health_check() is False


@respx.mock
@pytest.mark.asyncio
async def test_list_models(provider):
    respx.get("http://localhost:11434/api/tags").mock(
        return_value=httpx.Response(200, json={
            "models": [{"name": "llama3"}, {"name": "deepseek-coder"}]
        })
    )
    models = await provider.list_models()
    assert "llama3" in models
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_providers/test_ollama.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement OllamaProvider**

Create `modelmesh/providers/ollama.py`:

```python
import httpx
from typing import AsyncIterator
from .base import BaseProvider, ChatRequest, ChatResponse, EmbeddingRequest, EmbeddingResponse, Message


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return ChatResponse(
            model=data.get("model", request.model),
            content=data["message"]["content"],
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        if content := chunk.get("message", {}).get("content"):
                            yield content

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_providers/test_ollama.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/providers/ollama.py tests/test_providers/test_ollama.py
git commit -m "feat: add OllamaProvider with health check and streaming"
```

---

## Task 7: OpenAIProvider

**Files:**
- Create: `modelmesh/providers/openai_provider.py`
- Create: `tests/test_providers/test_openai_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_providers/test_openai_provider.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from modelmesh.providers.openai_provider import OpenAIProvider
from modelmesh.providers.base import ChatRequest, Message


@pytest.fixture
def provider():
    return OpenAIProvider(api_key="sk-test")


@pytest.mark.asyncio
async def test_chat_returns_response(provider):
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello!"
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 5

    with patch.object(provider._client.chat.completions, "create", new=AsyncMock(return_value=mock_response)):
        req = ChatRequest(model="gpt-4o", messages=[Message(role="user", content="Hi")])
        resp = await provider.chat(req)
        assert resp.content == "Hello!"
        assert resp.model == "gpt-4o"


@pytest.mark.asyncio
async def test_health_check_true(provider):
    with patch.object(provider._client.models, "list", new=AsyncMock(return_value=MagicMock())):
        assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_health_check_false_on_auth_error(provider):
    from openai import AuthenticationError
    import httpx
    mock_req = MagicMock(spec=httpx.Request)
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    with patch.object(provider._client.models, "list",
                      new=AsyncMock(side_effect=AuthenticationError("bad key", request=mock_req, response=mock_resp))):
        assert await provider.health_check() is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_providers/test_openai_provider.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement OpenAIProvider**

Create `modelmesh/providers/openai_provider.py`:

```python
from typing import AsyncIterator
from openai import AsyncOpenAI, AuthenticationError, APIConnectionError
from .base import BaseProvider, ChatRequest, ChatResponse, EmbeddingRequest, EmbeddingResponse


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str | None = None):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        kwargs = dict(model=request.model, messages=messages, temperature=request.temperature)
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        resp = await self._client.chat.completions.create(**kwargs)
        return ChatResponse(
            model=resp.model,
            content=resp.choices[0].message.content,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        stream = await self._client.chat.completions.create(
            model=request.model, messages=messages,
            temperature=request.temperature, stream=True,
        )
        async for chunk in stream:
            if content := chunk.choices[0].delta.content:
                yield content

    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse:
        inputs = request.input if isinstance(request.input, list) else [request.input]
        resp = await self._client.embeddings.create(model=request.model, input=inputs)
        return EmbeddingResponse(
            model=resp.model,
            embeddings=[d.embedding for d in resp.data],
            prompt_tokens=resp.usage.prompt_tokens,
        )

    async def health_check(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except (AuthenticationError, APIConnectionError):
            return False

    async def list_models(self) -> list[str]:
        resp = await self._client.models.list()
        return [m.id for m in resp.data]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_providers/test_openai_provider.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/providers/openai_provider.py tests/test_providers/test_openai_provider.py
git commit -m "feat: add OpenAIProvider with embeddings and streaming"
```

---

## Task 8: Rule Router

**Files:**
- Create: `modelmesh/router/rule_router.py`
- Create: `tests/test_rule_router.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_rule_router.py`:

```python
import pytest
from unittest.mock import AsyncMock
from modelmesh.router.rule_router import RuleRouter
from modelmesh.registry.model_registry import ModelRegistry, ModelEntry
from modelmesh.providers.base import BaseProvider
from pathlib import Path


@pytest.fixture
def registry():
    return ModelRegistry(Path("config/models.yaml"))


@pytest.fixture
def mock_ollama():
    p = AsyncMock(spec=BaseProvider)
    p.health_check.return_value = True
    return p


@pytest.fixture
def mock_openai():
    p = AsyncMock(spec=BaseProvider)
    p.health_check.return_value = True
    return p


@pytest.fixture
def router(registry, mock_ollama, mock_openai):
    return RuleRouter(
        registry=registry,
        providers={"ollama": mock_ollama, "openai": mock_openai},
        default_local_first=True,
    )


@pytest.mark.asyncio
async def test_explicit_model_resolves_to_provider(router, mock_ollama):
    provider, model = await router.resolve("llama3")
    assert provider is mock_ollama
    assert model == "llama3"


@pytest.mark.asyncio
async def test_explicit_openai_model(router, mock_openai):
    provider, model = await router.resolve("gpt-4o")
    assert provider is mock_openai


@pytest.mark.asyncio
async def test_auto_resolves_to_default(router, mock_ollama):
    provider, model = await router.resolve("auto")
    assert provider is mock_ollama   # local_first=True, ollama healthy


@pytest.mark.asyncio
async def test_auto_falls_back_when_ollama_down(registry, mock_ollama, mock_openai):
    mock_ollama.health_check.return_value = False
    router = RuleRouter(
        registry=registry,
        providers={"ollama": mock_ollama, "openai": mock_openai},
        default_local_first=True,
    )
    provider, model = await router.resolve("auto")
    assert provider is mock_openai


@pytest.mark.asyncio
async def test_unknown_model_raises(router):
    with pytest.raises(ValueError, match="Unknown model"):
        await router.resolve("does-not-exist")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_rule_router.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement RuleRouter**

Create `modelmesh/router/rule_router.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_rule_router.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add modelmesh/router/rule_router.py tests/test_rule_router.py
git commit -m "feat: add RuleRouter with local-first auto-routing and fallback"
```

---

## Task 9: Observability (Structured Logging)

**Files:**
- Create: `modelmesh/observability/logging.py`

- [ ] **Step 1: Implement structured logger**

Create `modelmesh/observability/logging.py`:

```python
import logging
import sys
from pythonjsonlogger import jsonlogger


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
```

- [ ] **Step 2: Commit**

```bash
git add modelmesh/observability/logging.py
git commit -m "feat: add structured JSON logging"
```

---

## Task 10: API Layer — /v1/models and /v1/chat/completions

**Files:**
- Create: `modelmesh/api/v1/models.py`
- Create: `modelmesh/api/v1/chat.py`
- Create: `tests/test_api/test_chat.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from modelmesh.providers.base import ChatResponse

@pytest.fixture
def mock_chat_response():
    return ChatResponse(
        model="llama3",
        content="Test response",
        prompt_tokens=5,
        completion_tokens=10,
        id="chatcmpl-test",
    )
```

Create `tests/test_api/test_chat.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from modelmesh.main import create_app
from modelmesh.providers.base import ChatResponse

# Patch the router at the module level BEFORE TestClient starts the lifespan.
# We override the module-level _router directly so the lifespan's set_router()
# call is irrelevant — our patch replaces the return value of get_router().
@pytest.fixture
def mock_router():
    router = AsyncMock()
    return router

@pytest.fixture
def client(mock_router, mock_chat_response):
    mock_provider = AsyncMock()
    mock_provider.chat = AsyncMock(return_value=mock_chat_response)
    mock_router.resolve = AsyncMock(return_value=(mock_provider, "llama3"))
    with patch("modelmesh.api.v1.chat._router", mock_router):
        with TestClient(create_app()) as c:
            yield c, mock_router, mock_provider


def test_chat_completions_returns_200(client, mock_chat_response):
    c, _, _ = client
    resp = c.post("/v1/chat/completions", json={
        "model": "llama3",
        "messages": [{"role": "user", "content": "Hello"}],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Test response"
    assert data["model"] == "llama3"
    assert "usage" in data


def test_chat_completions_unknown_model_returns_404(mock_chat_response):
    mock_router = AsyncMock()
    mock_router.resolve = AsyncMock(side_effect=ValueError("Unknown model: 'bad'"))
    with patch("modelmesh.api.v1.chat._router", mock_router):
        with TestClient(create_app()) as c:
            resp = c.post("/v1/chat/completions", json={
                "model": "bad",
                "messages": [{"role": "user", "content": "Hello"}],
            })
            assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api/test_chat.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement API routes**

Create `modelmesh/api/v1/models.py`:

```python
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
```

Create `modelmesh/api/v1/chat.py`:

```python
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
    # opening chunk with role
    yield f"data: {json.dumps({'id': resp_id, 'model': model, 'choices': [{'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
    async for token in provider.stream_chat(request):
        chunk = {"id": resp_id, "model": model, "choices": [{"delta": {"content": token}, "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"
    # closing chunk
    yield f"data: {json.dumps({'id': resp_id, 'model': model, 'choices': [{'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_api/test_chat.py -v
```
Expected: 2 PASSED (after main.py is created in next task — come back and run this then)

---

## Task 11: FastAPI App Entry Point

**Files:**
- Create: `modelmesh/main.py`

- [ ] **Step 1: Implement app factory**

Create `modelmesh/main.py`:

```python
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
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("modelmesh.main:app", host=settings.host, port=settings.port, reload=True)
```

- [ ] **Step 2: Run all tests**

```bash
pytest -v
```
Expected: all tests PASS

- [ ] **Step 3: Smoke test locally (optional but recommended)**

```bash
MODELMESH_PORT=8000 python -m modelmesh.main
# In another terminal:
curl http://localhost:8000/v1/models
```
Expected: `{"object":"list","data":[...]}`

- [ ] **Step 4: Commit**

```bash
git add modelmesh/main.py modelmesh/api/ tests/
git commit -m "feat: wire up FastAPI app with lifespan provider init"
```

---

## Task 12: /v1/embeddings Endpoint

**Files:**
- Create: `modelmesh/api/v1/embeddings.py`
- Create: `tests/test_api/test_embeddings.py`
- Modify: `modelmesh/main.py` (include embeddings router)

- [ ] **Step 1: Write the failing test**

Create `tests/test_api/test_embeddings.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from modelmesh.main import create_app
from modelmesh.providers.base import EmbeddingResponse


def test_embeddings_returns_200():
    mock_router = AsyncMock()
    mock_provider = AsyncMock()
    mock_provider.embeddings = AsyncMock(return_value=EmbeddingResponse(
        model="text-embedding-ada-002",
        embeddings=[[0.1, 0.2, 0.3]],
        prompt_tokens=4,
    ))
    mock_router.resolve = AsyncMock(return_value=(mock_provider, "text-embedding-ada-002"))

    with patch("modelmesh.api.v1.embeddings._router", mock_router):
        with TestClient(create_app()) as c:
            resp = c.post("/v1/embeddings", json={
                "model": "text-embedding-ada-002",
                "input": "Hello world",
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert data["model"] == "text-embedding-ada-002"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_api/test_embeddings.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Implement embeddings endpoint**

Create `modelmesh/api/v1/embeddings.py`:

```python
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
```

- [ ] **Step 4: Wire into main.py**

In `modelmesh/main.py`, add these imports and registrations:

```python
# Add to imports
from modelmesh.api.v1 import embeddings as embeddings_module
from modelmesh.api.v1.embeddings import router as embeddings_router

# Add inside lifespan after chat_module.set_router(router):
embeddings_module.set_router(router)

# Add inside create_app() after app.include_router(chat_router):
app.include_router(embeddings_router)
```

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add modelmesh/api/v1/embeddings.py tests/test_api/test_embeddings.py modelmesh/main.py
git commit -m "feat: add /v1/embeddings endpoint"
```

---

## Task 13: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache optimization)
# Copy source before pip install — hatchling needs the package present
COPY pyproject.toml .
COPY modelmesh/ modelmesh/
RUN pip install --no-cache-dir .

# Copy config (separate layer — changes frequently)
COPY config/ config/

# Non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "modelmesh.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create .dockerignore**

```
__pycache__/
*.pyc
*.pyo
.git/
.env
tests/
*.egg-info/
dist/
.venv/
```

- [ ] **Step 3: Build and verify**

```bash
docker build -t modelmesh:dev .
```
Expected: Build completes without error.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile with non-root user"
```

---

## Task 14: docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  gateway:
    build: .
    image: modelmesh:dev
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY:-}
      - MODELMESH_OLLAMA_BASE_URL=${OLLAMA_URL:-http://host.docker.internal:11434}
      - MODELMESH_LOG_LEVEL=INFO
    volumes:
      - ./config:/app/config:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Optional: uncomment to enable Redis caching (Phase 2)
  # redis:
  #   image: redis:7-alpine
  #   ports:
  #     - "6379:6379"
```

- [ ] **Step 2: Test docker-compose**

```bash
docker compose up --build -d
curl http://localhost:8000/v1/models
docker compose down
```
Expected: Returns model list JSON.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add docker-compose with gateway service"
```

---

## Task 15: Kubernetes Manifests

**Files:**
- Create: `k8s/configmap.yaml`
- Create: `k8s/secret.yaml`
- Create: `k8s/deployment.yaml`
- Create: `k8s/service.yaml`

- [ ] **Step 1: Create ConfigMap (mounts config YAML files)**

Create `k8s/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: modelmesh-config
  labels:
    app: modelmesh
data:
  models.yaml: |
    models:
      gpt-4o:
        provider: openai
        context_window: 128000
        cost_per_1k_tokens: 0.005
      gpt-4o-mini:
        provider: openai
        context_window: 128000
        cost_per_1k_tokens: 0.00015
      llama3:
        provider: ollama
        context_window: 8192
        cost_per_1k_tokens: 0.0
      deepseek-coder:
        provider: ollama
        context_window: 16384
        cost_per_1k_tokens: 0.0
      phi3-mini:
        provider: ollama
        context_window: 4096
        cost_per_1k_tokens: 0.0
    defaults:
      chat: llama3
      fallback: gpt-4o-mini
  routing.yaml: |
    routing:
      local_first: true
      intent_map:
        code:
          primary: deepseek-coder
          fallback: gpt-4o
```

- [ ] **Step 2: Create Secret template (never commit real keys)**

Create `k8s/secret.yaml`:

```yaml
# DO NOT commit real keys. Apply manually:
# kubectl create secret generic modelmesh-secrets \
#   --from-literal=openai-api-key=sk-... \
#   --from-literal=gateway-admin-key=your-admin-key
apiVersion: v1
kind: Secret
metadata:
  name: modelmesh-secrets
  labels:
    app: modelmesh
type: Opaque
stringData:
  openai-api-key: "REPLACE_ME"
  gateway-admin-key: "REPLACE_ME"
```

- [ ] **Step 3: Create Deployment**

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: modelmesh
  labels:
    app: modelmesh
spec:
  replicas: 2
  selector:
    matchLabels:
      app: modelmesh
  template:
    metadata:
      labels:
        app: modelmesh
    spec:
      containers:
        - name: gateway
          image: modelmesh:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          env:
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: modelmesh-secrets
                  key: openai-api-key
                  optional: true
            - name: MODELMESH_GATEWAY_ADMIN_KEY
              valueFrom:
                secretKeyRef:
                  name: modelmesh-secrets
                  key: gateway-admin-key
            - name: MODELMESH_MODELS_CONFIG_PATH
              value: /app/config/models.yaml
            - name: MODELMESH_ROUTING_CONFIG_PATH
              value: /app/config/routing.yaml
          volumeMounts:
            - name: config
              mountPath: /app/config
              readOnly: true
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /v1/models
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /v1/models
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: config
          configMap:
            name: modelmesh-config
```

- [ ] **Step 4: Create Service**

Create `k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: modelmesh
  labels:
    app: modelmesh
spec:
  selector:
    app: modelmesh
  ports:
    - name: http
      port: 80
      targetPort: 8000
  type: ClusterIP
---
# Optional LoadBalancer for direct external access
# Change type to LoadBalancer or add an Ingress for production
```

- [ ] **Step 5: Validate manifests**

```bash
kubectl apply --dry-run=client -f k8s/
```
Expected: All resources validated without error.

- [ ] **Step 6: Commit**

```bash
git add k8s/
git commit -m "chore: add Kubernetes manifests (Deployment, Service, ConfigMap, Secret)"
```

---

## Task 16: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

```markdown
# ModelMesh

A centralized, OpenAI-compatible LLM gateway. Route requests to Ollama, OpenAI, Anthropic, and HuggingFace from a single endpoint.

## Quickstart (Docker)

\```bash
# 1. Copy env template
cp .env.example .env
# Edit .env — add OPENAI_API_KEY if you have one

# 2. Start
docker compose up --build

# 3. Test
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "auto", "messages": [{"role": "user", "content": "Hello!"}]}'
\```

## VS Code / IDE Integration

Point any OpenAI-compatible extension at:
- **Base URL:** `http://localhost:8000/v1`
- **API Key:** any value (no auth in Phase 1)

Works with: Continue, CodeGPT, Cursor, and others.

## Kubernetes Deployment

\```bash
# Build and push image
docker build -t your-registry/modelmesh:latest .
docker push your-registry/modelmesh:latest

# Create secrets (never commit real keys)
kubectl create secret generic modelmesh-secrets \
  --from-literal=openai-api-key=sk-... \
  --from-literal=gateway-admin-key=change-me

# Deploy
kubectl apply -f k8s/
kubectl get pods -l app=modelmesh
\```

## Configuration

Edit `config/models.yaml` to add/remove models.
Edit `config/routing.yaml` to adjust routing rules.
In Kubernetes, update the ConfigMap and rollout restart:
\```bash
kubectl apply -f k8s/configmap.yaml
kubectl rollout restart deployment/modelmesh
\```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (optional if using Ollama only) |
| `MODELMESH_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `MODELMESH_PORT` | `8000` | Listen port |
| `MODELMESH_LOG_LEVEL` | `INFO` | Log level |
| `MODELMESH_GATEWAY_ADMIN_KEY` | `dev-admin-key` | Bootstrap admin key |
```

- [ ] **Step 2: Create .env.example**

```bash
# .env.example
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
MODELMESH_OLLAMA_BASE_URL=http://localhost:11434
MODELMESH_LOG_LEVEL=INFO
MODELMESH_GATEWAY_ADMIN_KEY=change-me-in-production
```

- [ ] **Step 3: Commit**

```bash
git add README.md .env.example
git commit -m "docs: add README with Docker and Kubernetes quickstart"
```

---

## Final Verification

- [ ] Run full test suite:
  ```bash
  pytest -v --tb=short
  ```
  Expected: all tests PASS, no warnings

- [ ] Build Docker image:
  ```bash
  docker build -t modelmesh:dev .
  ```
  Expected: builds successfully

- [ ] Run docker-compose and hit all endpoints:
  ```bash
  docker compose up -d
  curl http://localhost:8000/v1/models
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"auto","messages":[{"role":"user","content":"Say hello"}]}'
  docker compose down
  ```

- [ ] Validate K8s manifests:
  ```bash
  kubectl apply --dry-run=client -f k8s/
  ```

- [ ] Final commit:
  ```bash
  git tag v0.1.0
  ```
