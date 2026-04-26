import { Link, useNavigate } from 'react-router-dom'
import { LayoutDashboard, LogIn, LogOut, UserPlus } from 'lucide-react'
import MotionToggle from './MotionToggle'
import Logo from './Logo'
import { useAuth } from '../context/useAuth'

const TopNavbar = () => {
  const navigate = useNavigate()
  const { isAuthenticated, logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="glass-nav sticky top-4 z-20 rounded-2xl px-6 py-3.5">
      <div className="flex items-center justify-between">
        <Logo compact />
        <div className="flex items-center gap-3 text-sm">
          <MotionToggle />
          {isAuthenticated ? (
            <>
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 font-semibold text-white transition hover:bg-white/10"
              >
                <LayoutDashboard size={16} />
                Dashboard
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 font-semibold text-white transition hover:bg-white/10"
              >
                <LogOut size={16} />
                Logout
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 rounded-xl px-4 py-2 font-semibold text-white transition hover:bg-white/10"
              >
                <LogIn size={16} />
                Login
              </Link>
              <Link
                to="/signup"
                className="grad-btn grad-btn-b inline-flex items-center gap-1.5 rounded-xl px-4 py-2 font-semibold"
              >
                <UserPlus size={16} />
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

export default TopNavbar
