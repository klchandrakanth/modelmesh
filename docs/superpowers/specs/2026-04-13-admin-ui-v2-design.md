# ModelMesh Admin UI v2 — Design Spec

**Date:** 2026-04-13  
**Status:** Approved  
**Scope:** PostgreSQL persistence, JWT auth with forced password change, model CRUD, Recharts dashboards

---

## 1. Goals

1. Replace the static `X-Admin-Key` admin auth with a proper username/password login backed by PostgreSQL.
2. Persist the model registry in PostgreSQL so models can be added, edited, and disabled from the UI without touching YAML.
3. Replace hand-rolled SVG charts with Recharts — time-series line chart + donut breakdowns.

---

## 2. Architecture Overview

No new top-level services beyond what was already planned. PostgreSQL joins the existing docker-compose stack alongside Redis.

```
docker-compose
  ├── gateway      FastAPI — LLM API + admin REST
  ├── admin-ui     React + nginx
  ├── redis        (existing)
  └── postgres     NEW — models + users
```

Provider API keys remain in environment variables. No credentials are stored in the database.

---

## 3. Database (PostgreSQL 16, bundled)

### 3.1 Connection

- Driver: `asyncpg` + SQLAlchemy Core (no ORM, no Alembic)
- Pool wired to `app.state.db` on startup, closed on shutdown
- `DATABASE_URL` env var, default: `postgresql+asyncpg://modelmesh:devpassword@postgres/modelmesh`
- In production, override `DATABASE_URL` to a managed Postgres and remove the `postgres` service from compose

### 3.2 Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    must_change_pw BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS models (
    name              TEXT PRIMARY KEY,
    provider          TEXT NOT NULL,
    context_window    INTEGER NOT NULL DEFAULT 4096,
    cost_per_1k       REAL NOT NULL DEFAULT 0.0,
    is_default        BOOLEAN NOT NULL DEFAULT FALSE,
    is_fallback       BOOLEAN NOT NULL DEFAULT FALSE,
    enabled           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.3 Seeding

On application startup, after schema creation:

- **users**: if the table is empty, insert `admin` / `admin` (bcrypt-hashed) with `must_change_pw = TRUE`.
- **models**: if the table is empty, read `config/models.yaml` and insert all entries. After this one-time migration the YAML file is ignored at runtime.

### 3.4 docker-compose changes

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: modelmesh
    POSTGRES_USER: modelmesh
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-devpassword}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD", "pg_isready", "-U", "modelmesh"]
    interval: 10s
    timeout: 5s
    retries: 5

volumes:
  postgres_data:
```

Gateway gets `DATABASE_URL` in its environment block and `depends_on: postgres: condition: service_healthy`.

---

## 4. Auth System

### 4.1 Backend endpoints

```
POST /admin/auth/login
  Body: { username: str, password: str }
  Response: { access_token: str, must_change_pw: bool }

POST /admin/auth/change-password
  Header: Authorization: Bearer <token>
  Body: { current_password: str, new_password: str }
  Response: { access_token: str }   ← fresh token with must_change_pw: false
```

### 4.2 Token format

- Algorithm: HS256 JWT
- Payload: `{ sub: username, must_change_pw: bool, exp: now + 8h }`
- Secret: `JWT_SECRET` env var. If unset, a random 32-byte secret is generated at startup (tokens invalidated on restart — acceptable for dev).

### 4.3 Endpoint protection

- All existing `X-Admin-Key` dependencies replaced by a `require_jwt` FastAPI dependency.
- If `must_change_pw` is `true` in the token, every protected endpoint returns `403 { "detail": "password_change_required" }`.
- `/admin/auth/login` is fully public (no auth required).
- `/admin/auth/change-password` requires a valid Bearer token (any `must_change_pw` state) but is exempt from the `password_change_required` gate — this is how users with `must_change_pw: true` can still complete the flow. The endpoint verifies `current_password` against the DB record for the user in the token's `sub` claim.
- After a successful password change the client MUST discard the old token and store the new one. The old token is not server-side invalidated (no blocklist — acceptable for single-admin dev use).

### 4.4 Frontend routing

```
/login                 LoginPage              public
/change-password       ChangePasswordPage     token required (any state)
/dashboard             Dashboard              token + pw changed
/models                Models                 token + pw changed
/keys                  Keys                   token + pw changed
/logs                  Logs                   token + pw changed
```

A `<PrivateRoute>` wrapper reads the JWT from `localStorage`:
- No token → redirect to `/login`
- `must_change_pw: true` → redirect to `/change-password`

The `X-Admin-Key` header in `api/client.ts` is replaced by `Authorization: Bearer <token>` read from `localStorage`.

### 4.5 First-login UX

1. User opens admin UI → no token → `/login`
2. Enters `admin / admin` → receives token with `must_change_pw: true`
3. Immediately redirected to `/change-password`
4. Sets new password → receives fresh token with `must_change_pw: false`
5. Redirected to `/dashboard`

---

## 5. Model Management (CRUD)

### 5.1 New backend endpoints

```
POST   /admin/models
  Body: { name, provider, context_window, cost_per_1k, is_default, is_fallback }

PATCH  /admin/models/{name}
  Body: any subset of model fields (including { enabled: false } to disable)

DELETE /admin/models/{name}
  Hard-delete: removes row from DB permanently
```

Note: **disable** (reversible) = `PATCH { enabled: false }`. **Delete** (permanent) = `DELETE`. These are two distinct operations, both exposed in the UI.

Existing `GET /admin/models` unchanged in shape; adds `enabled` field to each entry.

When `is_default` or `is_fallback` is set to `true`, the endpoint clears the flag on any previous default/fallback model (only one of each allowed).

### 5.2 Registry changes

`ModelRegistry` gains an async `load_from_db(db)` method called at startup and after any write endpoint. The YAML `_load` path remains for the one-time seed but is no longer called during normal operation.

### 5.3 Frontend — Models page

- **"+ Add Model" button** → modal: name (text), provider (dropdown: ollama / openai / anthropic / huggingface), context window (number), cost/1k tokens (number), default toggle, fallback toggle.
- **Edit (pencil icon)** per row → same modal pre-filled via `PATCH`.
- **Disable/Enable toggle** per row → `PATCH { enabled: false/true }` (soft, reversible).
- **Delete (trash icon)** per row → `DELETE` (permanent, requires confirmation dialog).
- Disabled models shown as grayed-out rows, still visible but marked `[disabled]`.

---

## 6. Charts & Metrics

### 6.1 New dependency

`recharts@^2.12` added to `admin-ui/package.json`. No other charting library.

`TimeSeriesChart.tsx` uses two `<YAxis>` components with distinct `yAxisId` props (`"requests"` and `"latency"`) and each `<Line>` is tagged with the matching `yAxisId`. This is the standard Recharts pattern for dual-axis charts.

### 6.2 New backend endpoint

```
GET /admin/metrics/timeseries?window=1h|6h|24h
Response: {
  window: "1h",
  buckets: [
    { ts: <unix>, requests: int, errors: int, avg_latency_ms: float }
  ]
}
```

Computed from the in-memory `RequestLog` (capacity: 500 entries, `MAX_ENTRIES`). Bucket size: 5 minutes. The endpoint filters the ring buffer to the requested window and groups by 5-minute floor. The response includes an `actual_from` field (earliest timestamp in the buffer) so the client can display a notice if less data is available than the selected window (e.g., gateway restarted recently).

### 6.3 Dashboard changes

| Panel | Before | After |
|---|---|---|
| 4 metric cards | unchanged | unchanged |
| Requests by model | SVG bar chart | Donut chart (Recharts `PieChart`) |
| Requests by provider | SVG bar chart | Donut chart |
| Requests by status | SVG bar chart | Donut chart |
| Time-series | (none) | Dual-axis `LineChart`: requests/min (left), avg latency ms (right). Window selector: 1h / 6h / 24h |

The hand-rolled `BarChart` SVG component is removed. `ProviderDot` and `MetricCard` are kept unchanged.

---

## 7. Files Changed / Created

### Backend (new)

| File | Purpose |
|---|---|
| `modelmesh/db/connection.py` | asyncpg pool setup, `get_db()` dependency |
| `modelmesh/db/schema.py` | `CREATE TABLE IF NOT EXISTS` statements + seed logic |
| `modelmesh/api/admin/auth_endpoints.py` | `/admin/auth/login`, `/admin/auth/change-password` |
| `modelmesh/api/admin/auth.py` | Replace `require_admin_key` with `require_jwt` dependency |

### Backend (modified)

| File | Change |
|---|---|
| `modelmesh/main.py` | Wire DB pool, run schema + seed, register auth router, add postgres to startup |
| `modelmesh/registry/model_registry.py` | Add `load_from_db()`, `add_model()`, `update_model()`, `disable_model()` |
| `modelmesh/api/admin/models.py` | Add `POST`, `PATCH`, `DELETE` endpoints |
| `modelmesh/api/admin/metrics.py` | Add `GET /admin/metrics/timeseries` |
| `modelmesh/api/admin/keys.py` | Swap auth dependency to `require_jwt` |
| `modelmesh/api/admin/logs.py` | Swap auth dependency to `require_jwt` |
| `modelmesh/api/admin/health.py` | Swap auth dependency to `require_jwt` |
| `docker-compose.yml` | Add `postgres` service + volume, update gateway env |

### Frontend (new)

| File | Purpose |
|---|---|
| `admin-ui/src/pages/Login.tsx` | Login form |
| `admin-ui/src/pages/ChangePassword.tsx` | Forced password change form |
| `admin-ui/src/components/PrivateRoute.tsx` | Auth guard + must_change_pw redirect |
| `admin-ui/src/components/charts/DonutChart.tsx` | Recharts wrapper for breakdown donuts |
| `admin-ui/src/components/charts/TimeSeriesChart.tsx` | Recharts dual-axis line chart |

### Frontend (modified)

| File | Change |
|---|---|
| `admin-ui/src/App.tsx` | Add `/login`, `/change-password` routes; wrap protected routes in `<PrivateRoute>` |
| `admin-ui/src/api/client.ts` | Replace `X-Admin-Key` with `Authorization: Bearer` from localStorage; add `login()`, `changePassword()`, `fetchTimeseries()`, model mutation calls |
| `admin-ui/src/pages/Dashboard.tsx` | Replace SVG `BarChart` with donut charts + time-series panel |
| `admin-ui/src/pages/Models.tsx` | Add add/edit/disable UI |
| `admin-ui/src/components/Layout.tsx` | Add logout button (clears localStorage, redirects to `/login`) |

---

## 8. Out of Scope

- Password reset via email (no SMTP configured)
- Multi-user support (single admin account for now)
- Provider API key management in the UI (keys stay in env vars)
- Alembic migrations (schema managed via `CREATE TABLE IF NOT EXISTS`)
- Request log persistence to DB (ring buffer stays in-memory)
- Token blacklisting / server-side logout: logout clears `localStorage` only; a stolen token remains valid until its 8-hour expiry. Acceptable for single-admin dev use.
