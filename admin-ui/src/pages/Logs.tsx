import { useEffect, useState } from 'react'
import { fetchLogs, LogEntry } from '../api/client'

const statusColor: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
  stream: 'bg-blue-100 text-blue-700',
}

function fmt(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export default function Logs() {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState({ model: '', provider: '', status: '' })

  const load = () => {
    setLoading(true)
    fetchLogs({
      limit: 100,
      model: filter.model || undefined,
      provider: filter.provider || undefined,
      status: filter.status || undefined,
    })
      .then(setEntries)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [filter.model, filter.provider, filter.status])

  const totalCost = entries.reduce((s, e) => s + e.cost_usd, 0)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">Request Logs</h1>
        <button
          onClick={load}
          className="text-sm text-brand-600 hover:text-brand-700 font-medium"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          type="text"
          placeholder="Filter by model…"
          value={filter.model}
          onChange={(e) => setFilter((f) => ({ ...f, model: e.target.value }))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <input
          type="text"
          placeholder="Filter by provider…"
          value={filter.provider}
          onChange={(e) => setFilter((f) => ({ ...f, provider: e.target.value }))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <select
          value={filter.status}
          onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All statuses</option>
          <option value="success">success</option>
          <option value="error">error</option>
          <option value="stream">stream</option>
        </select>
        {(filter.model || filter.provider || filter.status) && (
          <button
            onClick={() => setFilter({ model: '', provider: '', status: '' })}
            className="text-sm text-gray-400 hover:text-gray-600"
          >
            ✕ Clear
          </button>
        )}
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      {loading ? (
        <p className="text-gray-400">Loading…</p>
      ) : (
        <>
          <div className="text-xs text-gray-400 mb-2">
            {entries.length} entries · est. cost ${totalCost.toFixed(5)}
          </div>
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
            <table className="w-full text-sm min-w-[800px]">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Time</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Model</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Provider</th>
                  <th className="text-center px-3 py-3 font-semibold text-gray-600">Status</th>
                  <th className="text-right px-3 py-3 font-semibold text-gray-600">Latency</th>
                  <th className="text-right px-3 py-3 font-semibold text-gray-600">Tokens</th>
                  <th className="text-right px-3 py-3 font-semibold text-gray-600">Cost</th>
                  <th className="text-left px-3 py-3 font-semibold text-gray-600">Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {entries.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-3 py-2 text-gray-400 text-xs font-mono whitespace-nowrap">
                      {fmt(e.timestamp)}
                    </td>
                    <td className="px-3 py-2 font-medium text-gray-800 whitespace-nowrap">
                      {e.model}
                    </td>
                    <td className="px-3 py-2 text-gray-500 capitalize">{e.provider}</td>
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          statusColor[e.status] ?? 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {e.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500 whitespace-nowrap">
                      {e.latency_ms > 0 ? `${e.latency_ms} ms` : '—'}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500">
                      {e.prompt_tokens + e.completion_tokens > 0
                        ? `${e.prompt_tokens}+${e.completion_tokens}`
                        : '—'}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-500">
                      {e.cost_usd > 0 ? `$${e.cost_usd.toFixed(5)}` : '—'}
                    </td>
                    <td className="px-3 py-2 text-gray-400 text-xs max-w-xs truncate">
                      {e.request_preview || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {entries.length === 0 && (
              <p className="text-center text-gray-400 py-8 text-sm">
                No requests yet — send a chat completion to see logs here
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
