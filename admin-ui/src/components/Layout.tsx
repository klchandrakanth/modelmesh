import { NavLink, Outlet } from 'react-router-dom'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: '📊' },
  { to: '/models', label: 'Models', icon: '🤖' },
  { to: '/keys', label: 'API Keys', icon: '🔑' },
  { to: '/logs', label: 'Logs', icon: '📋' },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 bg-gray-900 text-white flex flex-col">
        <div className="px-5 py-5 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-xl">⬡</span>
            <span className="font-bold text-lg tracking-tight">ModelMesh</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">Admin Dashboard</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`
              }
            >
              <span>{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-gray-700 flex items-center justify-between">
          <span className="text-xs text-gray-500">v0.3.0</span>
          <button
            onClick={() => {
              localStorage.removeItem('mm_token')
              window.location.href = '/login'
            }}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
