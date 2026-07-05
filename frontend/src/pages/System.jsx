import { useEffect, useState } from 'react'
import { ShieldCheck, Database, Gauge, Cpu, Lock, EyeOff, FileClock, UserCheck } from 'lucide-react'
import { api } from '../lib/api.js'

const SECURITY_FEATURES = [
  { icon: EyeOff, name: 'PII redaction', desc: 'Emails & phones stripped before external API calls', phase: 'Phase 5' },
  { icon: ShieldCheck, name: 'Prompt-injection screening', desc: 'Scraped web content is screened before reaching agents', phase: 'Phase 5' },
  { icon: FileClock, name: 'Audit trail', desc: 'Every scoring decision logged with reasoning', phase: 'Phase 5' },
  { icon: UserCheck, name: 'Human approval gate', desc: 'No email is sent without explicit approval', phase: 'Active' },
]

export default function System() {
  const [health, setHealth] = useState(null)
  const [budget, setBudget] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => {})
    api.budget().then(setBudget).catch(() => {})
  }, [])

  const providers = ['gemini', 'tavily', 'serper', 'firecrawl']
  const cap = budget?.budget_per_provider ?? 50

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white">System</h1>
        <p className="mt-1 text-sm text-slate-400">
          Cost protection, security posture, and runtime status.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="card p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Cpu size={13} /> Model
          </div>
          <div className="mt-2 font-mono text-sm text-white">{health?.model ?? '—'}</div>
          <div className="mt-1 text-xs text-slate-500">all agents share this model</div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Database size={13} /> Data mode
          </div>
          <div className={`mt-2 text-sm font-semibold ${health?.mock_mode ? 'text-amber-400' : 'text-emerald-400'}`}>
            {health?.mock_mode ? 'Mock mode — zero external API cost' : 'Live mode — real web research'}
          </div>
          <div className="mt-1 text-xs text-slate-500">toggle via MOCK_MODE in .env</div>
        </div>
        <div className="card p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
            <Gauge size={13} /> Daily budget
          </div>
          <div className="mt-2 text-sm font-semibold text-white">{cap} calls / provider / day</div>
          <div className="mt-1 text-xs text-slate-500">hard stop with graceful degradation</div>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-sm font-semibold text-slate-300">API budget usage today</h2>
        <p className="mt-1 text-xs text-slate-500">
          Every external call passes through the budget guard. Cached results cost nothing.
        </p>
        <div className="mt-5 space-y-4">
          {providers.map((p) => {
            const used = budget?.used?.[p] ?? 0
            const pct = Math.min(100, (used / cap) * 100)
            return (
              <div key={p}>
                <div className="mb-1.5 flex justify-between text-xs">
                  <span className="font-medium capitalize text-slate-300">{p}</span>
                  <span className="text-slate-500">{used} / {cap}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    className={`h-full rounded-full transition-all ${
                      pct > 80 ? 'bg-rose-500' : pct > 50 ? 'bg-amber-500' : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.max(pct, 1)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <Lock size={15} className="text-indigo-400" /> Security posture
        </h2>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          {SECURITY_FEATURES.map(({ icon: Icon, name, desc, phase }) => (
            <div key={name} className="flex gap-3 rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                phase === 'Active' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-800 text-slate-500'
              }`}>
                <Icon size={16} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-200">{name}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    phase === 'Active'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-slate-800 text-slate-500'
                  }`}>
                    {phase}
                  </span>
                </div>
                <div className="mt-0.5 text-xs text-slate-500">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
