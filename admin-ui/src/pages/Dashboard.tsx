import { useEffect, useState, type ReactNode } from 'react'
import {
  fetchMetrics, fetchHealth, fetchTimeseries,
  type MetricsSummary, type HealthResult, type TimeseriesResponse,
} from '../api/client'
import DonutChart from '../components/charts/DonutChart'
import TimeSeriesChart from '../components/charts/TimeSeriesChart'

type Window = '1h' | '6h' | '24h'

function MetricCard({ label, value, sub, color = 'blue' }: {
  label: string; value: string; sub?: string; color?: 'blue' | 'green' | 'yellow' | 'purple'
}) {
  const accent: Record<string, string> = {
    blue: 'text-blue-700', green: 'text-green-700',
    yellow: 'text-yellow-700', purple: 'text-purple-700',
  }
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <p className="text-sm text-gray-500 font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent[color]}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

function ProviderDot({ healthy }: { healthy: boolean }) {
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${healthy ? 'bg-green-500' : 'bg-red-500'}`} />
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null)
  const [health, setHealth] = useState<HealthResult | null>(null)
  const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null)
  const [window, setWindow] = useState<Window>('1h')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = () => {
    Promise.all([fetchMetrics(), fetchHealth(), fetchTimeseries(window)])
      .then(([m, h, ts]) => { setMetrics(m); setHealth(h); setTimeseries(ts); setError(null) })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(); const id = setInterval(load, 15_000); return () => clearInterval(id) }, [window])

  if (loading) return <PageShell title="Dashboard"><p className="text-gray-400">Loading…</p></PageShell>
  if (error) return <PageShell title="Dashboard"><p className="text-red-500 text-sm">{error}</p></PageShell>

  return (
    <PageShell title="Dashboard">
      {/* Metric cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
        <MetricCard label="Total Requests" value={String(metrics?.total_requests ?? 0)} sub="since last restart" color="blue" />
        <MetricCard label="Success Rate" value={metrics ? (metrics.success_rate * 100).toFixed(1) + '%' : '—'} color="green" />
        <MetricCard label="Avg Latency" value={metrics ? metrics.avg_latency_ms + ' ms' : '—'} color="yellow" />
        <MetricCard label="Estimated Cost" value={metrics ? '$' + metrics.total_cost_usd.toFixed(4) : '—'} sub={`${metrics?.total_tokens ?? 0} tokens`} color="purple" />
      </div>

      {/* Time-series */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mb-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-700">Request Volume & Latency</h2>
          <div className="flex gap-1">
            {(['1h', '6h', '24h'] as Window[]).map((w) => (
              <button
                key={w}
                onClick={() => setWindow(w)}
                className={`px-3 py-1 text-xs rounded-lg font-medium transition-colors ${
                  window === w ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {w}
              </button>
            ))}
          </div>
        </div>
        <TimeSeriesChart buckets={timeseries?.buckets ?? []} />
        {timeseries && timeseries.buckets.length > 0 && (
          <p className="text-xs text-gray-400 mt-2">
            Data from {new Date(timeseries.actual_from * 1000).toLocaleTimeString()} · 5-min buckets
          </p>
        )}
      </div>

      {/* Breakdown donuts */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-4">By Model</h2>
          <DonutChart data={metrics?.requests_by_model ?? {}} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-4">By Provider</h2>
          <DonutChart data={metrics?.requests_by_provider ?? {}} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <h2 className="font-semibold text-gray-700 mb-4">By Status</h2>
          <DonutChart data={metrics?.requests_by_status ?? {}} />
        </div>
      </div>

      {/* Provider health */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm mt-4">
        <h2 className="font-semibold text-gray-700 mb-4">Provider Health</h2>
        {health && Object.keys(health.providers).length > 0 ? (
          <div className="space-y-3">
            {Object.entries(health.providers).map(([name, info]) => (
              <div key={name} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <ProviderDot healthy={info.healthy} />
                  <span className="font-medium capitalize">{name}</span>
                  <span className="text-xs text-gray-400">{info.provider_class}</span>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${info.healthy ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {info.healthy ? 'healthy' : 'down'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-gray-400 text-sm">No providers configured</p>
        )}
      </div>
    </PageShell>
  )
}

function PageShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-gray-800 mb-6">{title}</h1>
      {children}
    </div>
  )
}
