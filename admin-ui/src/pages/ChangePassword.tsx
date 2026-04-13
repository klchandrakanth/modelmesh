import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { changePassword } from '../api/client'

export default function ChangePassword() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (next !== confirm) { setError('Passwords do not match'); return }
    if (next.length < 8) { setError('New password must be at least 8 characters'); return }
    setLoading(true)
    setError(null)
    try {
      const res = await changePassword(current, next)
      localStorage.setItem('mm_token', res.access_token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-8">
        <h1 className="text-lg font-bold text-gray-800 mb-2">Change Password</h1>
        <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg p-3 mb-5">
          You must change your password before continuing.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          {(['Current password', 'New password', 'Confirm new password'] as const).map((label, i) => {
            const [val, set] = [[current, setCurrent], [next, setNext], [confirm, setConfirm]][i] as [string, (v: string) => void]
            return (
              <div key={label}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input
                  type="password"
                  value={val}
                  onChange={(e) => set(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  required
                />
              </div>
            )
          })}
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? 'Saving…' : 'Set new password'}
          </button>
        </form>
      </div>
    </div>
  )
}
