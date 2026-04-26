import { Link } from 'react-router-dom'
import { ScanSearch } from 'lucide-react'

const Logo = ({ compact = false, to = '/' }) => {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-2 text-white transition hover:opacity-90"
      aria-label="Go to home page"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/15 ring-1 ring-white/30">
        <ScanSearch size={16} strokeWidth={2.25} />
      </div>
      <span className={`font-semibold  tracking-wide ${compact ? 'text-base' : 'text-xl'}`}>
        Resume Rank
      </span>
    </Link>
  )
}

export default Logo
