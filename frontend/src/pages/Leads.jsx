import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api } from '../lib/api.js'
import TierBadge from '../components/TierBadge.jsx'

const FILTERS = ['All', 'Hot', 'Warm', 'Cold']

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('All')
  const navigate = useNavigate()

  useEffect(() => {
    api.leads().then((d) => setLeads(d.leads)).catch(() => {})
  }, [])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return leads
      .filter((l) => filter === 'All' || l.tier === filter)
      .filter(
        (l) =>
          !q ||
          (l.name || '').toLowerCase().includes(q) ||
          l.company.toLowerCase().includes(q) ||
          (l.industry || '').toLowerCase().includes(q) ||
          (l.notes || '').toLowerCase().includes(q),
      )
      .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
  }, [leads, query, filter])

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white">Leads</h1>
        <p className="mt-1 text-sm text-slate-400">
          {leads.length} leads in CRM, ranked by score. Click a row for the full analysis.
        </p>
      </header>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, company, industry…"
            className="w-full rounded-xl border border-slate-800 bg-slate-900/60 py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder:text-slate-500 outline-none transition focus:border-indigo-500/50"
          />
        </div>
        <div className="flex gap-1 rounded-xl border border-slate-800 bg-slate-900/60 p-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
                filter === f ? 'bg-indigo-500 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wider text-slate-500">
              <th className="px-5 py-3.5 font-medium">Company</th>
              <th className="px-5 py-3.5 font-medium">Industry</th>
              <th className="px-5 py-3.5 font-medium">CRM notes</th>
              <th className="px-5 py-3.5 font-medium">Score</th>
              <th className="px-5 py-3.5 font-medium">Tier</th>
              <th className="px-5 py-3.5 font-medium">Email</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((l) => (
              <tr
                key={l.lead_id}
                onClick={() => navigate(`/leads/${l.lead_id}`)}
                className="cursor-pointer border-b border-slate-800/50 transition hover:bg-indigo-500/5"
              >
                <td className="px-5 py-4">
                  <div className="font-semibold text-white">{l.company}</div>
                  <div className="text-xs text-slate-500">{l.lead_id}</div>
                </td>
                <td className="px-5 py-4 text-slate-400">{l.industry}</td>
                <td className="max-w-xs truncate px-5 py-4 text-slate-400">{l.notes || '—'}</td>
                <td className="px-5 py-4">
                  {l.score != null ? (
                    <div className="flex items-center gap-2.5">
                      <span className="w-7 font-bold text-white">{l.score}</span>
                      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                          style={{ width: `${l.score}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="px-5 py-4"><TierBadge tier={l.tier} /></td>
                <td className="px-5 py-4 text-xs">
                  {l.email_status === 'pending_approval' && <span className="text-amber-400">Awaiting approval</span>}
                  {l.email_status === 'approved_and_sent' && <span className="text-emerald-400">Sent</span>}
                  {l.email_status === 'rejected' && <span className="text-rose-400">Rejected</span>}
                  {!l.email_status && <span className="text-slate-600">No draft</span>}
                </td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-10 text-center text-slate-500">
                  No leads match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
