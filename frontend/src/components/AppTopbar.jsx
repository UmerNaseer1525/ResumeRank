import { Link, useNavigate } from 'react-router-dom'
import { LogOut, Settings, UserRound } from 'lucide-react'
import MotionToggle from './MotionToggle'
import Logo from './Logo'
import { useAuth } from '../context/useAuth'

const AppTopbar = () => {
  const navigate = useNavigate()
  const { logout, user } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="glass-nav flex h-16 items-center justify-between px-5">
      <Logo compact />
      <div className="flex items-center gap-4 text-white">
        <MotionToggle />
      
        <button className="rounded-lg bg-white/10 p-2 text-white/90 transition hover:scale-105 hover:bg-white/20 hover:text-white">
          <Settings size={16} />
        </button> 
        <Link
          to="/profile"
          className="flex items-center gap-2 rounded-full border border-white/50 bg-white/15 px-3 py-1.5 text-sm font-bold"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/90 text-blue-700">
            <UserRound size={14} />
          </span>
          <span className="hidden md:inline">{user?.fullName || 'Profile'}</span>
        </Link>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-lg bg-white/10 p-2 text-white/90 transition hover:scale-105 hover:bg-white/20 hover:text-white"
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  )
}

export default AppTopbar
