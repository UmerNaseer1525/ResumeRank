import { NavLink } from 'react-router-dom'
import { BarChart3, BriefcaseBusiness, LayoutDashboard, UploadCloud } from 'lucide-react'

const links = [
  { label: 'Recruiter Dashboard', to: '/dashboard', icon: LayoutDashboard },
  { label: 'Job Openings', to: '/jobs', icon: BriefcaseBusiness },
  { label: 'Upload Candidate Resumes', to: '/upload', icon: UploadCloud },
  { label: 'Candidate Rankings', to: '/ranking-results', icon: BarChart3 },
]

const Sidebar = () => {
  return (
    <aside className="w-full border-r border-white/10 bg-white/5 md:w-56">
      <nav className="space-y-1 p-3">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm font-semibold transition ${
                isActive
                  ? 'border-white/25 bg-white/20 text-white shadow'
                  : 'border-transparent text-indigo-100 hover:border-white/20 hover:bg-white/10 hover:text-white'
              }`
            }
          >
            <link.icon size={17} strokeWidth={2.1} />
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar
