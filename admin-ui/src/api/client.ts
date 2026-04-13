const API_BASE = import.meta.env.VITE_API_BASE ?? ''

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('mm_token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers ?? {}) },
  })
  if (res.status === 401) {
    localStorage.removeItem('mm_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const login = (username: string, password: string) =>
  request<{ access_token: string; must_change_pw: boolean }>('/admin/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

export const changePassword = (current_password: string, new_password: string) =>
  request<{ access_token: string }>('/admin/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password, new_password }),
  })

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface MetricsSummary {
  total_requests: number
  success_rate: number
  avg_latency_ms: number
  total_tokens: number
  total_cost_usd: number
  requests_by_model: Record<string, number>
  requests_by_provider: Record<string, number>
  requests_by_status: Record<string, number>
}

export const fetchMetrics = () => request<MetricsSummary>('/admin/metrics')

export interface TimeseriesBucket {
  ts: number
  requests: number
  errors: number
  avg_latency_ms: number
}

export interface TimeseriesResponse {
  window: string
  actual_from: number
  buckets: TimeseriesBucket[]
}

export const fetchTimeseries = (window: '1h' | '6h' | '24h') =>
  request<TimeseriesResponse>(`/admin/metrics/timeseries?window=${window}`)

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthResult {
  providers: Record<string, { healthy: boolean; provider_class: string }>
}

export const fetchHealth = () => request<HealthResult>('/admin/health')

// ── Models ────────────────────────────────────────────────────────────────────

export interface ModelInfo {
  name: string
  provider: string
  context_window: number
  cost_per_1k_tokens: number
  is_default: boolean
  is_fallback: boolean
  provider_healthy: boolean | null
  enabled: boolean
}

export const fetchModels = () =>
  request<{ models: ModelInfo[] }>('/admin/models').then((r) => r.models)

export interface ModelPayload {
  name: string
  provider: string
  context_window: number
  cost_per_1k: number
  is_default: boolean
  is_fallback: boolean
}

export const createModel = (payload: ModelPayload) =>
  request<{ name: string; status: string }>('/admin/models', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const updateModel = (name: string, fields: Partial<ModelPayload & { enabled: boolean }>) =>
  request<{ name: string; status: string }>(`/admin/models/${name}`, {
    method: 'PATCH',
    body: JSON.stringify(fields),
  })

export const deleteModel = (name: string) =>
  request<{ name: string; status: string }>(`/admin/models/${name}`, {
    method: 'DELETE',
  })

// ── Logs ──────────────────────────────────────────────────────────────────────

export interface LogEntry {
  id: string
  timestamp: number
  model: string
  provider: string
  status: string
  latency_ms: number
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  request_preview: string
}

export const fetchLogs = (params?: {
  limit?: number
  model?: string
  provider?: string
  status?: string
}) => {
  const q = new URLSearchParams()
  if (params?.limit) q.set('limit', String(params.limit))
  if (params?.model) q.set('model', params.model)
  if (params?.provider) q.set('provider', params.provider)
  if (params?.status) q.set('status', params.status)
  return request<{ count: number; entries: LogEntry[] }>(
    `/admin/logs${q.toString() ? '?' + q.toString() : ''}`,
  ).then((r) => r.entries)
}

// ── Keys ──────────────────────────────────────────────────────────────────────

export interface KeyInfo {
  id: string
  name: string
  rate_limit_per_minute: number
  routing_policy: Record<string, unknown>
}

export interface CreateKeyResponse extends KeyInfo {
  secret: string
  warning: string
}

export const fetchKeys = () =>
  request<{ keys: KeyInfo[] }>('/admin/keys').then((r) => r.keys)

export const createKey = (name: string, rate_limit_per_minute = 60) =>
  request<CreateKeyResponse>('/admin/keys', {
    method: 'POST',
    body: JSON.stringify({ name, rate_limit_per_minute }),
  })

export const revokeKey = (id: string) =>
  request<{ deleted: string }>(`/admin/keys/${id}`, { method: 'DELETE' })
