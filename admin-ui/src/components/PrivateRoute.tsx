import { Navigate, Outlet } from 'react-router-dom'

function getTokenPayload(): { must_change_pw?: boolean } | null {
  const token = localStorage.getItem('mm_token')
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    // Check expiry
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('mm_token')
      return null
    }
    return payload
  } catch {
    return null
  }
}

export default function PrivateRoute() {
  const payload = getTokenPayload()
  if (!payload) return <Navigate to="/login" replace />
  if (payload.must_change_pw) return <Navigate to="/change-password" replace />
  return <Outlet />
}
