import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid, LabelList,
} from 'recharts'
import { Flame, ThermometerSun, Snowflake, Target, ArrowRight, Search, Scale, Send } from 'lucide-react'
import { api, TIER_STYLES } from '../lib/api.js'
import TierBadge from '../components/TierBadge.jsx'

const PIPELINE_STEPS = [
  { icon: Search, name: 'Research Agent', desc: 'CRM + web intel via MCP tools' },
  { icon: Scale, name: 'Qualification Agent', desc: 'Score 0-100 → Hot / Warm / Cold' },
  { icon: Send, name: 'Outreach Agent', desc: 'Report + email, human approval' },
]

function StatCard({ label, value, sub, icon: Icon, accent }) {
  return (
    <div className="card flex items-center gap-4 p-5">
      <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${accent}`}>
        <Icon size={20} />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value}</div>
        <div className="text-xs text-slate-400">{label}</div>
        {sub && <div className="text-[11px] text-slate-500">{sub}</div>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [leads, setLeads] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    api.leads().then((d) => setLeads(d.leads)).catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="card mt-10 p-8 text-center text-sm text-rose-400">
        Cannot reach the backend: {error}. Start it with{' '}
        <code className="font-mono text-slate-300">uv run uvicorn app.api.server:app --port 8100</code>
      </div>
    )
  }

  const scored = leads.filter((l) => l.score != null)
  const counts = { Hot: 0, Warm: 0, Cold: 0 }
  scored.forEach((l) => { counts[l.tier] = (counts[l.tier] ?? 0) + 1 })
  const avg = scored.length ? Math.round(scored.reduce((s, l) => s + l.score, 0) / scored.length) : 0

  const pieData = Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([tier, value]) => ({ name: tier, value }))

  const barData = [...scored]
    .sort((a, b) => b.score - a.score)
    .map((l) => ({ name: l.company.split(' ')[0], score: l.score, tier: l.tier }))

  const topLeads = [...scored].sort((a, b) => b.score - a.score).slice(0, 3)

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-400">
            Your pipeline at a glance — every score comes with reasoning attached.
          </p>
        </div>
        <Link
          to="/leads"
          className="flex items-center gap-2 rounded-xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:bg-indigo-400"
        >
          View all leads <ArrowRight size={15} />
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard label="Total leads" value={leads.length} sub="in CRM" icon={Target}
          accent="bg-indigo-500/15 text-indigo-400" />
        <StatCard label="Hot leads" value={counts.Hot} sub="contact now" icon={Flame}
          accent="bg-rose-500/15 text-rose-400" />
        <StatCard label="Warm leads" value={counts.Warm} sub="follow up soon" icon={ThermometerSun}
          accent="bg-amber-500/15 text-amber-400" />
        <StatCard label="Avg. score" value={avg} sub="out of 100" icon={Snowflake}
          accent="bg-sky-500/15 text-sky-400" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="card p-5 xl:col-span-3">
          <h2 className="text-sm font-semibold text-slate-300">Lead scores</h2>
          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 18, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip
                  cursor={{ fill: 'rgba(99,102,241,0.06)' }}
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 13 }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Bar dataKey="score" radius={[8, 8, 0, 0]} maxBarSize={52}>
                  <LabelList dataKey="score" position="top" fill="#94a3b8" fontSize={12} />
                  {barData.map((d) => (
                    <Cell key={d.name} fill={TIER_STYLES[d.tier]?.chart ?? '#818cf8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5 xl:col-span-2">
          <h2 className="text-sm font-semibold text-slate-300">Tier distribution</h2>
          <div className="mt-3 h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} dataKey="value" innerRadius={52} outerRadius={78}
                  paddingAngle={4} strokeWidth={0}>
                  {pieData.map((d) => (
                    <Cell key={d.name} fill={TIER_STYLES[d.name]?.chart} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 12, fontSize: 13 }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex justify-center gap-4">
            {pieData.map((d) => (
              <div key={d.name} className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="h-2 w-2 rounded-full" style={{ background: TIER_STYLES[d.name]?.chart }} />
                {d.name} ({d.value})
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="card p-5 xl:col-span-3">
          <h2 className="text-sm font-semibold text-slate-300">Top priorities</h2>
          <div className="mt-3 space-y-2">
            {topLeads.map((l, i) => (
              <Link
                key={l.lead_id}
                to={`/leads/${l.lead_id}`}
                className="flex items-center gap-4 rounded-xl border border-slate-800/60 bg-slate-900/40 px-4 py-3 transition hover:border-indigo-500/40 hover:bg-slate-800/40"
              >
                <span className="w-6 text-center text-lg font-bold text-slate-600">#{i + 1}</span>
                <div className="flex-1">
                  <div className="text-sm font-semibold text-white">{l.name}</div>
                  <div className="text-xs text-slate-400">{l.title} · {l.company}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-white">{l.score}</div>
                  <div className="text-[10px] text-slate-500">score</div>
                </div>
                <TierBadge tier={l.tier} />
              </Link>
            ))}
          </div>
        </div>

        <div className="card p-5 xl:col-span-2">
          <h2 className="text-sm font-semibold text-slate-300">Agent pipeline</h2>
          <div className="mt-4 space-y-0">
            {PIPELINE_STEPS.map(({ icon: Icon, name, desc }, i) => (
              <div key={name} className="flex gap-3">
                <div className="flex flex-col items-center">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                    <Icon size={16} />
                  </div>
                  {i < PIPELINE_STEPS.length - 1 && <div className="my-1 w-px flex-1 bg-slate-800" />}
                </div>
                <div className="pb-5">
                  <div className="text-sm font-semibold text-slate-200">{name}</div>
                  <div className="text-xs text-slate-500">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
