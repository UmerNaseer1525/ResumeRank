import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/useAuth'

const PublicOnlyRoute = () => {
  const { isAuthenticated, isInitializing } = useAuth()

  if (isInitializing) {
    return <div className="glass rounded-2xl p-6 text-indigo-100">Loading session...</div>
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}

export default PublicOnlyRoute
