import { useEffect, useState, type FormEvent } from 'react'
import {
  fetchModels, createModel, updateModel, deleteModel,
  type ModelInfo, type ModelPayload,
} from '../api/client'

const providerColor: Record<string, string> = {
  ollama: 'bg-orange-100 text-orange-700',
  openai: 'bg-green-100 text-green-700',
  anthropic: 'bg-purple-100 text-purple-700',
  huggingface: 'bg-yellow-100 text-yellow-700',
}

const PROVIDERS = ['ollama', 'openai', 'anthropic', 'huggingface']

export default function Models() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<ModelInfo | null>(null)

  const reload = () => {
    setLoading(true)
    fetchModels()
      .then(setModels)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(reload, [])

  const handleToggleEnabled = async (m: ModelInfo) => {
    try {
      await updateModel(m.name, { enabled: !m.enabled })
      reload()
    } catch (e) { setError((e as Error).message) }
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Permanently delete model "${name}"? This cannot be undone.`)) return
    try {
      await deleteModel(name)
      reload()
    } catch (e) { setError((e as Error).message) }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-800">Models</h1>
        <div className="flex gap-2">
          <button onClick={reload} className="text-sm text-brand-600 hover:text-brand-700 font-medium">↻ Refresh</button>
          <button
            onClick={() => { setEditing(null); setShowForm(true) }}
            className="px-4 py-2 bg-brand-600 text-white text-sm font-medium rounded-lg hover:bg-brand-700"
          >
            + Add Model
          </button>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      {loading ? <p className="text-gray-400">Loading…</p> : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="w-full text-sm min-w-[700px]">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Model</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Provider</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Context</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">$/1k</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-600">Health</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-600">Role</th>
                <th className="text-center px-4 py-3 font-semibold text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {models.map((m) => (
                <tr key={m.name} className={`hover:bg-gray-50 transition-colors ${!m.enabled ? 'opacity-50' : ''}`}>
                  <td className="px-4 py-3 font-medium text-gray-800">
                    {m.name}
                    {!m.enabled && <span className="ml-2 text-xs text-gray-400">[disabled]</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${providerColor[m.provider] ?? 'bg-gray-100 text-gray-600'}`}>
                      {m.provider}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500">{m.context_window.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-gray-500">
                    {m.cost_per_1k_tokens === 0 ? <span className="text-green-600 font-medium">free</span> : `$${m.cost_per_1k_tokens}`}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {m.provider_healthy === null ? <span className="text-gray-400 text-xs">—</span>
                      : m.provider_healthy
                        ? <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                        : <span className="inline-block w-2 h-2 rounded-full bg-red-500" />}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {m.is_default && <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 font-medium">default</span>}
                      {m.is_fallback && <span className="px-1.5 py-0.5 text-xs rounded bg-amber-100 text-amber-700 font-medium">fallback</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => { setEditing(m); setShowForm(true) }}
                        className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleToggleEnabled(m)}
                        className="text-xs text-gray-500 hover:text-gray-700 font-medium"
                      >
                        {m.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        onClick={() => handleDelete(m.name)}
                        className="text-xs text-red-500 hover:text-red-700 font-medium"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {models.length === 0 && <p className="text-center text-gray-400 py-8 text-sm">No models configured</p>}
        </div>
      )}

      {showForm && (
        <ModelForm
          initial={editing}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload() }}
        />
      )}
    </div>
  )
}

function ModelForm({
  initial, onClose, onSaved,
}: {
  initial: ModelInfo | null
  onClose: () => void
  onSaved: () => void
}) {
  const isEdit = initial !== null
  const [name, setName] = useState(initial?.name ?? '')
  const [provider, setProvider] = useState(initial?.provider ?? 'ollama')
  const [context, setContext] = useState(initial?.context_window ?? 4096)
  const [cost, setCost] = useState(initial?.cost_per_1k_tokens ?? 0)
  const [isDefault, setIsDefault] = useState(initial?.is_default ?? false)
  const [isFallback, setIsFallback] = useState(initial?.is_fallback ?? false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (isEdit) {
        await updateModel(initial!.name, { provider, context_window: context, cost_per_1k: cost, is_default: isDefault, is_fallback: isFallback })
      } else {
        await createModel({ name, provider, context_window: context, cost_per_1k: cost, is_default: isDefault, is_fallback: isFallback } as ModelPayload)
      }
      onSaved()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">{isEdit ? `Edit ${initial!.name}` : 'Add Model'}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model name</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" autoFocus />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500">
              {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Context window</label>
              <input type="number" value={context} min={1} onChange={(e) => setContext(Number(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Cost / 1k tokens</label>
              <input type="number" value={cost} min={0} step={0.0001} onChange={(e) => setCost(Number(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} className="rounded" />
              Default
            </label>
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input type="checkbox" checked={isFallback} onChange={(e) => setIsFallback(e.target.checked)} className="rounded" />
              Fallback
            </label>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
              {saving ? 'Saving…' : isEdit ? 'Update' : 'Add'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
