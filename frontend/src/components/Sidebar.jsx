import { NavLink } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { LayoutDashboard, Users, MessageSquareText, Activity, Radar } from 'lucide-react'
import { api } from '../lib/api.js'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/leads', label: 'Leads', icon: Users },
  { to: '/assistant', label: 'AI Assistant', icon: MessageSquareText },
  { to: '/system', label: 'System', icon: Activity },
]

export default function Sidebar() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: 'offline' }))
  }, [])

  const online = health?.status === 'ok'

  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-slate-800/80 bg-slate-950/80 backdrop-blur">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/25">
          <Radar size={20} className="text-white" />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-white">LeadPilot AI</div>
          <div className="text-[11px] text-slate-500">Lead Qualification</div>
        </div>
      </div>

      <nav className="mt-2 flex-1 space-y-1 px-3">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-500/15 text-indigo-300'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mx-3 mb-4 rounded-xl border border-slate-800/80 bg-slate-900/60 px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-400 animate-soft-pulse' : 'bg-rose-500'}`}
          />
          <span className="text-xs font-medium text-slate-300">
            {online ? 'Agent online' : 'Backend offline'}
          </span>
        </div>
        {health?.mock_mode && (
          <div className="mt-1.5 text-[11px] text-amber-400/90">
            Mock mode — zero API cost
          </div>
        )}
        {online && (
          <div className="mt-1 truncate text-[11px] text-slate-500 font-mono">{health.model}</div>
        )}
      </div>
    </aside>
  )
}
