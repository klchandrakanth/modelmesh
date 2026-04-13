# ModelMesh — Enhanced Design Specification

**Date:** 2026-04-03  
**Status:** Approved  
**Audience:** Personal use + small team/startup  
**Tech Stack:** Python / FastAPI + React + shadcn/ui

---

## 1. Objective

Build a centralized ModelMesh that:

- Provides a unified, OpenAI-compatible API for multiple LLM providers (Ollama, OpenAI, Anthropic, HuggingFace)
- Routes requests intelligently using a semantic intent classifier
- Works out-of-the-box with zero configuration (local-first default)
- Provides an Admin UI for managing models, API keys, and routing rules
- Eliminates the need to update individual apps when models or providers change

**Key design principle:** Smart routing is progressive enhancement. An explicit `model=` parameter always bypasses the classifier. `model=auto` triggers it.

---

## 2. Architecture

```
Clients (VS Code / CLI / Apps)       Admin UI (React + shadcn/ui)
              │                              │
    ┌─────────▼──────────────────────────────▼──────┐
    │               FastAPI Gateway                  │
    │   /v1/*  (LLM API)    |   /admin/*  (REST)     │
    └────────────┬───────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │   Auth + Rate Limit     │  API key check, per-key quotas
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────┐
    │      Smart Router       │  Classifier → model selection
    │  (intent + rules +      │  + explicit override support
    │   fallback chains)      │  Local-first default if Ollama running
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────┐
    │   Provider Adapters     │  OpenAI / Claude / Ollama / HF
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────┐
    │   Observability +       │  Structured logs, token cost,
    │   Cache (Redis opt.)    │  Prometheus metrics
    └─────────────────────────┘
```

**One FastAPI application** serves both the LLM API (`/v1/*`) and the Admin REST API (`/admin/*`). No separate microservice complexity.

---

## 3. Core Components

### 3.1 API Layer

OpenAI-compatible endpoints:
- `POST /v1/chat/completions` — chat with streaming (SSE) support
- `POST /v1/embeddings` — text embeddings
- `GET /v1/models` — list available models

Admin endpoints:
- `GET/POST/DELETE /admin/models` — model registry management
- `GET/POST/DELETE /admin/keys` — API key management
- `GET /admin/metrics` — usage statistics
- `GET /admin/logs` — request log viewer

### 3.2 Auth & Rate Limiting

- API key validation via `X-API-Key` header or `Authorization: Bearer <key>`
- Per-key rate limits and budget caps
- Phase 1: keys stored in `config/keys.yaml`. A **bootstrap key** (`GATEWAY_ADMIN_KEY` env var) is always valid and grants admin access — used to create the first real API key via the admin endpoint.

`config/keys.yaml` schema:
```yaml
keys:
  - id: key-abc123
    key: "sk-local-abc123"        # hashed with bcrypt in storage
    name: "VS Code personal"
    rate_limit: 1000/min
    budget_usd: 10.0              # monthly cap, null = unlimited
    enabled: true
```
- Phase 2: `/admin/keys` CRUD endpoints ship alongside auth to enable key management without touching YAML
- Phase 3+: keys optionally stored in PostgreSQL

CORS: The gateway enables CORS for `http://localhost:3000` (Admin UI) in development. In production, the allowed origin is configurable via `CORS_ALLOW_ORIGINS` env var.

### 3.3 Smart Router

The primary enhancement. Three sub-components:

**Intent Classifier**

Uses `sentence-transformers` (`all-MiniLM-L6-v2`, ~80MB) with **zero-shot nearest-centroid classification**. Each intent bucket is represented by 5–10 curated example sentences embedded at startup. Incoming request content is embedded and compared via cosine similarity to each bucket's centroid. The highest-scoring bucket wins if its score exceeds a confidence threshold of **0.65**; otherwise the request falls back to the `factual` default bucket.

Example label sentences for `code`: `"Write a Python function"`, `"Fix this bug"`, `"Explain this code"`, `"Implement a REST endpoint"`, `"Debug this error"`.

Label sentences are stored in `config/routing.yaml` under `intent_labels:` and can be customized without code changes.

| Intent | Default Model | Fallback |
|--------|---------------|---------|
| `code` | `deepseek-coder` (Ollama) | `gpt-4o` |
| `summarize` | `llama3` (Ollama) | `claude-haiku` |
| `creative` | `claude-sonnet` | `gpt-4o` |
| `factual` | `llama3` (Ollama) | `gpt-4o-mini` |
| `long_form` | `claude-opus` | `gpt-4o` |
| `fast` | `phi3-mini` (Ollama) | `gpt-4o-mini` |

**Model Selector**

Given classified intent + request context:
1. Resolve primary model from intent map
2. Run health check on target provider (timeout: 2s, no retry — treat timeout as unavailable)
3. Check user budget remaining
4. Apply Routing Policy overrides
5. Fallback to next in chain if primary unavailable

Health checks are cached for 30 seconds per provider (circuit-breaker pattern). A provider that fails 3 consecutive health checks is marked `degraded` and skipped for 60 seconds before re-probing.

**Routing Policy**

Global defaults and per-key overrides live in `config/routing.yaml`. Per-key policies override the global default for keys that specify them:

```yaml
routing:
  # Global intent → model mapping (applies to all keys unless overridden)
  intent_map:
    code:
      primary: deepseek-coder
      fallback: gpt-4o
    summarize:
      primary: llama3
      fallback: claude-haiku
  # Global default policy
  default_policy:
    local_first: true            # prefer Ollama over cloud APIs
    max_cost_per_request: 0.05   # USD

  # Per-key policy overrides (keyed by API key ID)
  key_policies:
    key-abc123:
      local_first: false         # this key always uses cloud
      max_cost_per_request: 0.20
    key-team01:
      intent_map:
        code:
          primary: gpt-4o        # team prefers GPT-4 for code
          fallback: deepseek-coder
```

**Zero-config default:** On startup, gateway probes `localhost:11434` for Ollama. If available, all `model=auto` requests route there. If not, routes to the first configured cloud provider.

**Request routing decision tree:**

```
Request arrives with model=?
  ├── model == explicit name
  │     └── resolve via Model Registry → provider
  └── model == "auto" or absent
        ├── run Intent Classifier → intent bucket
        ├── Model Selector picks primary model
        ├── check availability + budget
        └── fallback if needed
```

### 3.4 Provider Abstraction Layer

All providers implement a common async interface:

```python
class BaseProvider:
    async def chat(self, request: ChatRequest) -> ChatResponse: ...
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[str]: ...
    async def embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse: ...
    async def health_check(self) -> bool: ...
    async def list_models(self) -> list[str]: ...
```

| Provider | Notes |
|----------|-------|
| `OllamaProvider` | Auto-detects running models via Ollama REST API. No API key needed. |
| `OpenAIProvider` | Standard `openai` Python SDK. Supports GPT-4o, o1, embeddings. |
| `AnthropicProvider` | `anthropic` Python SDK. Claude Sonnet, Haiku, Opus. |
| `HuggingFaceProvider` | Inference API + optional local `transformers` fallback. |

Adding a new provider = implement `BaseProvider` + add one YAML entry.

### 3.5 Model Registry

`config/models.yaml` — source of truth for all available models:

```yaml
models:
  gpt-4o:
    provider: openai
    context_window: 128000
    cost_per_1k_tokens: 0.005
  claude-sonnet:
    provider: anthropic
    context_window: 200000
    cost_per_1k_tokens: 0.003
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
```

Features: hot reload (file watcher, no restart required), per-model cost metadata, default + fallback model config.

### 3.6 Observability

- **Structured JSON logging** for every request, response, and error
- **Prometheus metrics** at `/metrics`:
  - `llm_request_total{provider, model, status}` — counter
  - `llm_latency_seconds{model}` — histogram
  - `llm_tokens_total{type}` — prompt + completion tokens
  - `llm_cost_usd_total{model}` — estimated cost
- Optional **Grafana dashboard** via docker-compose

### 3.7 Cache Layer (Optional, Phase 2)

- Redis-backed prompt cache
- Cache key: `sha256(model + canonicalized_messages)`
- TTL: configurable per model
- Bypass: include `"cache": false` in request metadata

### 3.8 Admin UI (Phase 3)

React + shadcn/ui dashboard with 5 pages:

1. **Dashboard** — live metrics: requests/min, cost today, top models used
2. **Models** — add/edit/disable models in the registry
3. **API Keys** — create/revoke keys, set quotas and per-key routing policies
4. **Routing Rules** — visual editor for intent→model mapping (no YAML needed)
5. **Logs** — searchable and filterable request log viewer

---

## 4. Data Models

### Request (OpenAI-compatible)
```json
{
  "model": "auto",
  "messages": [
    {"role": "user", "content": "Explain transformer architecture"}
  ],
  "temperature": 0.7,
  "stream": false
}
```

### Non-Streaming Response (OpenAI-compatible)
```json
{
  "id": "resp-abc123",
  "model": "llama3",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Transformer architecture is..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 85,
    "total_tokens": 97
  }
}
```

### Streaming Response (SSE, OpenAI-compatible)

When `"stream": true`, the endpoint returns `Content-Type: text/event-stream`. Each chunk follows OpenAI's streaming format:

```
data: {"id":"resp-abc123","model":"llama3","choices":[{"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"resp-abc123","model":"llama3","choices":[{"delta":{"content":"Transformer"},"finish_reason":null}]}

data: {"id":"resp-abc123","model":"llama3","choices":[{"delta":{"content":" architecture"},"finish_reason":null}]}

data: {"id":"resp-abc123","model":"llama3","choices":[{"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

The `stream_chat` method in `BaseProvider` must yield raw content strings; the API layer wraps them into the SSE envelope above.

---

## 5. Project Structure

```
modelmesh/
├── gateway/
│   ├── main.py                    # FastAPI app entry point
│   ├── api/
│   │   ├── v1/
│   │   │   ├── chat.py            # /v1/chat/completions
│   │   │   ├── embeddings.py      # /v1/embeddings
│   │   │   └── models.py          # /v1/models
│   │   └── admin/
│   │       ├── models.py          # /admin/models
│   │       ├── keys.py            # /admin/keys
│   │       ├── metrics.py         # /admin/metrics
│   │       └── logs.py            # /admin/logs
│   ├── router/
│   │   ├── smart_router.py        # Intent classifier + model selector
│   │   ├── rule_router.py         # Explicit routing rules
│   │   └── routing_policy.py      # Per-key policy enforcement
│   ├── providers/
│   │   ├── base.py                # BaseProvider ABC
│   │   ├── ollama.py
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── huggingface.py
│   ├── registry/
│   │   └── model_registry.py      # YAML-backed + hot reload
│   ├── auth/
│   │   └── api_keys.py            # Key validation + rate limiting
│   ├── cache/
│   │   └── redis_cache.py         # Redis prompt deduplication
│   ├── observability/
│   │   ├── logging.py             # Structured JSON logger
│   │   └── metrics.py             # Prometheus metrics
│   └── config/
│       └── settings.py            # Pydantic settings + YAML loader
├── admin-ui/
│   ├── src/
│   │   ├── components/            # shadcn/ui components
│   │   ├── pages/                 # Dashboard, Models, Keys, etc.
│   │   └── api/                   # Admin REST client
│   └── package.json
├── config/
│   ├── models.yaml
│   ├── routing.yaml
│   └── keys.yaml
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 6. Deployment

### Local Development
```bash
docker-compose up
```

Services: gateway (port 8000), Redis (optional), Grafana (optional)

### VS Code / IDE Integration
```json
{
  "apiBase": "http://localhost:8000/v1",
  "apiKey": "local-dev-key"
}
```
Compatible with Continue, CodeGPT, and any OpenAI-compatible client.

### Production
- Stateless FastAPI nodes behind NGINX load balancer
- Redis for caching + rate limit state
- PostgreSQL for key storage + audit logs
- Horizontal scaling via container replicas

---

## 7. Security

- Provider API keys stored in environment variables only (never in YAML)
- Admin UI requires separate admin API key
- Rate limiting protects against abuse
- Request/response logs exclude sensitive content by default (configurable)

---

## 8. Implementation Phases

### Phase 1 — Core Gateway (MVP)
**Goal:** Working gateway in < 30 minutes. Point VS Code at it and chat.

- FastAPI scaffold + OpenAI-compatible Pydantic models
- `OllamaProvider` + `OpenAIProvider`
- Static model registry (`models.yaml`)
- Rule-based router (explicit model name → provider)
- Local-first auto-routing (Ollama probe on startup)
- Structured logging
- Docker Compose
- README quickstart

**Deliverable:** `POST /v1/chat/completions` works with Ollama and OpenAI.

### Phase 2 — Smart Routing + Full Providers
- Intent Classifier (`sentence-transformers`)
- Model Selector + Routing Policy
- `AnthropicProvider` + `HuggingFaceProvider`
- API key auth + per-key rate limits
- Redis caching layer
- Prometheus metrics at `/metrics`
- Provider health checks + availability detection

**Deliverable:** `model=auto` routes intelligently. All 4 providers work.

### Phase 3 — Admin UI
- React + shadcn/ui (Vite scaffold)
- Admin REST API in FastAPI
- Dashboard, Models, Keys, Routing Rules, Logs pages
- Docker Compose update (admin-ui service on port 3000)

**Deliverable:** Full dashboard. No YAML editing needed for day-to-day operations.

---

## 9. Future Enhancements

- **LLM-as-Router** — Use GPT-3.5 or Ollama to make nuanced routing decisions for complex requests (two-tier with classifier)
- **Cost optimization engine** — Real-time cost tracking with automatic downgrade when budget thresholds are hit
- **Prompt versioning** — Store and A/B test prompt templates centrally
- **Multi-modal routing** — Image/audio/video request classification and routing
- **Plugin ecosystem** — Middleware hooks for custom pre/post processing

---

## 10. Verification Criteria

| Phase | Test |
|-------|------|
| Phase 1 | `docker-compose up` → `curl localhost:8000/v1/chat/completions` with `model=llama3` returns valid response |
| Phase 2 | `model=auto` request classifies correctly, routes to right provider; `/metrics` shows Prometheus data |
| Phase 3 | Admin UI loads at `localhost:3000`, shows live stats, allows adding a new model without editing YAML |
