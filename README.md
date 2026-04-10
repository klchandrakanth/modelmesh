# ModelMesh

A centralized, OpenAI-compatible LLM gateway. Route requests to Ollama, OpenAI, Anthropic, and HuggingFace from a single endpoint.

## Quickstart (Docker)

```bash
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
```

## VS Code / IDE Integration

Point any OpenAI-compatible extension at:
- **Base URL:** `http://localhost:8000/v1`
- **API Key:** any value (no auth in Phase 1)

Works with: Continue, CodeGPT, Cursor, and others.

## Local Development (without Docker)

```bash
pip install -e ".[dev]"
python -m modelmesh.main
```

Requires Ollama running at `http://localhost:11434` or an `OPENAI_API_KEY` set.

## Kubernetes Deployment

```bash
# Build and push image
docker build -t your-registry/modelmesh:latest .
docker push your-registry/modelmesh:latest

# Update image in k8s/deployment.yaml, then:

# Create secrets (never commit real keys)
kubectl create secret generic modelmesh-secrets \
  --from-literal=openai-api-key=sk-... \
  --from-literal=gateway-admin-key=change-me

# Deploy
kubectl apply -f k8s/
kubectl get pods -l app=modelmesh
```

## Updating Config in Kubernetes

Edit `k8s/configmap.yaml` then:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl rollout restart deployment/modelmesh
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | OpenAI API key (optional if using Ollama) |
| `MODELMESH_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `MODELMESH_PORT` | `8000` | Listen port |
| `MODELMESH_LOG_LEVEL` | `INFO` | Log level |
| `MODELMESH_GATEWAY_ADMIN_KEY` | `dev-admin-key` | Bootstrap admin key |

### Model Registry (`config/models.yaml`)

Add or remove models without code changes:

```yaml
models:
  my-custom-model:
    provider: ollama        # ollama | openai | anthropic
    context_window: 8192
    cost_per_1k_tokens: 0.0
defaults:
  chat: my-custom-model
  fallback: gpt-4o-mini
```

### Smart Routing

Send `model: "auto"` to let ModelMesh pick the best model:
- If Ollama is running → uses local model (free)
- If Ollama is down → falls back to configured cloud provider

Explicit model names bypass routing entirely.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat (OpenAI-compatible, supports streaming) |
| POST | `/v1/embeddings` | Text embeddings |
| GET | `/v1/models` | List available models |

## Architecture

```
Clients → FastAPI Gateway → Auth → Smart Router → Provider Adapters → LLM APIs
                                                                    ↑
                                                    Ollama (local) / OpenAI / Claude / HF
```

## Roadmap

- **Phase 2:** Semantic intent classifier, Anthropic + HuggingFace providers, API key auth, Redis caching, Prometheus metrics
- **Phase 3:** React + shadcn/ui Admin Dashboard (model mgmt, usage metrics, routing rules editor)
