import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Building2, Globe, Newspaper, TrendingUp, Layers, CheckCircle2,
  XCircle, Clock, Mail, Search, Scale, Send, Sparkles,
} from 'lucide-react'
import { api, TIER_STYLES } from '../lib/api.js'
import TierBadge from '../components/TierBadge.jsx'

const BREAKDOWN_LABELS = {
  industry_fit: 'Industry fit',
  company_size: 'Company size',
  engagement: 'Engagement',
  growth_signals: 'Growth signals',
  online_presence: 'Online presence',
}

const AGENT_ICONS = { research_agent: Search, qualification_agent: Scale, outreach_agent: Send }

function ScoreRing({ score, tier }) {
  const color = TIER_STYLES[tier]?.chart ?? '#818cf8'
  const r = 54
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-36 w-36">
      <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
        <circle cx="64" cy="64" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="64" cy="64" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-extrabold text-white">{score}</span>
        <span className="text-[10px] uppercase tracking-wider text-slate-500">of 100</span>
      </div>
    </div>
  )
}

export default function LeadDetail() {
  const { leadId } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [emailBusy, setEmailBusy] = useState(false)
  const [researchBusy, setResearchBusy] = useState(false)
  const [qualifyBusy, setQualifyBusy] = useState(false)

  useEffect(() => {
    api.leadDetail(leadId).then(setData).catch((e) => setError(e.message))
  }, [leadId])

  if (error) return <div className="card mt-10 p-8 text-center text-rose-400">{error}</div>
  if (!data) return <div className="mt-10 text-center text-slate-500">Loading…</div>

  const { lead, qualification: q } = data

  const handleResearch = async () => {
    setResearchBusy(true)
    try {
      await api.runResearch(leadId)
      const refreshed = await api.leadDetail(leadId)
      setData(refreshed)
    } catch (e) {
      setError(e.message)
    } finally {
      setResearchBusy(false)
    }
  }

  const handleQualify = async () => {
    setQualifyBusy(true)
    try {
      await api.qualifyLead(leadId)
      const refreshed = await api.leadDetail(leadId)
      setData(refreshed)
    } catch (e) {
      setError(e.message)
    } finally {
      setQualifyBusy(false)
    }
  }

  const handleEmail = async (action) => {
    setEmailBusy(true)
    try {
      const res = await api.emailAction(leadId, action)
      setData((d) => ({
        ...d,
        qualification: {
          ...d.qualification,
          draft_email: {
            ...d.qualification.draft_email,
            status: res.email_status,
            ...(res.delivery ? { delivery: res.delivery } : {}),
          },
        },
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setEmailBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <Link to="/leads" className="inline-flex items-center gap-1.5 text-sm text-slate-400 transition hover:text-slate-200">
        <ArrowLeft size={15} /> Back to leads
      </Link>

      <div className="card flex flex-wrap items-center gap-6 p-6">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-xl font-bold text-white">
          {(lead.company || lead.name || '?').slice(0, 2).toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white">{lead.company || lead.name}</h1>
            {q && <TierBadge tier={q.tier} size="lg" />}
            {q?.research_live && (
              <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-[11px] font-medium text-sky-400">
                live research
              </span>
            )}
            {q?.outreach_live && (
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-0.5 text-[11px] font-medium text-violet-400">
                live outreach
              </span>
            )}
            {q?.qualification_live && !q?.outreach_live && (
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
                live score
              </span>
            )}
            {q?.mock && !q?.qualification_live && (
              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-400">
                mock data
              </span>
            )}
          </div>
          <div className="mt-1 text-sm text-slate-400">
            {[lead.industry, lead.notes].filter(Boolean).join(' · ')}
          </div>
          <div className="mt-1 text-[11px] text-slate-600">
            CRM minimum data — click Research for Tavily + Firecrawl live intel
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex gap-2">
            <button
              onClick={handleQualify}
              disabled={qualifyBusy || researchBusy}
              className="flex items-center gap-2 rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-violet-500/25 transition hover:bg-violet-500 disabled:opacity-50"
            >
              <Scale size={14} />
              {qualifyBusy ? 'Running pipeline…' : 'Qualify + outreach'}
            </button>
            <button
              onClick={handleResearch}
              disabled={researchBusy || qualifyBusy}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/60 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/50 disabled:opacity-50"
            >
              <Search size={14} />
              {researchBusy ? 'Researching…' : 'Research only'}
            </button>
          </div>
          {q && (
            <div className="text-right text-xs text-slate-500">
              <div>Confidence {(q.confidence * 100).toFixed(0)}%</div>
              <div className="mt-0.5">Priority #{q.recommendation?.priority ?? '—'}</div>
              {q.research_live && (
                <div className="mt-0.5 text-sky-400">
                  Live research
                  {q.research_providers?.length ? ` (${q.research_providers.join(', ')})` : ''}
                </div>
              )}
              {q.outreach_live && (
                <div className="mt-0.5 text-violet-400">Live outreach applied</div>
              )}
              {q.qualification_live && !q.outreach_live && (
                <div className="mt-0.5 text-emerald-400">Live qualification applied</div>
              )}
              {q.research_live && !q.qualification_live && (
                <div className="mt-0.5 text-indigo-400">Live research only</div>
              )}
            </div>
          )}
        </div>
      </div>

      {!q && (
        <div className="card p-8 text-center text-sm text-slate-400">
          This lead hasn't been qualified yet. Run the pipeline from the AI Assistant.
        </div>
      )}

      {q && (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="card flex flex-col items-center gap-4 p-6">
              <h2 className="self-start text-sm font-semibold text-slate-300">Lead score</h2>
              <ScoreRing score={q.score} tier={q.tier} />
              <div className="w-full space-y-2.5">
                {Object.entries(q.score_breakdown).map(([k, v]) => (
                  <div key={k}>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-slate-400">{BREAKDOWN_LABELS[k] ?? k}</span>
                      <span className="font-semibold text-slate-200">{v}/20</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                        style={{ width: `${(v / 20) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card p-6 xl:col-span-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
                <Sparkles size={15} className="text-indigo-400" /> Why this score
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">{q.reasoning}</p>

              <h3 className="mt-6 text-sm font-semibold text-slate-300">Research findings</h3>
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                    <Building2 size={13} /> Company
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-300">{q.research_summary.company_overview}</p>
                </div>
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                    <Newspaper size={13} /> Recent news
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-slate-300">{q.research_summary.recent_news}</p>
                </div>
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                    <TrendingUp size={13} /> Growth signals
                  </div>
                  <ul className="mt-2 space-y-1 text-xs text-slate-300">
                    {q.research_summary.growth_signals.map((g) => <li key={g}>· {g}</li>)}
                  </ul>
                </div>
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
                    <Layers size={13} /> Tech stack
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {q.research_summary.tech_stack.map((t) => (
                      <span key={t} className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] text-slate-300">{t}</span>
                    ))}
                  </div>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
                <Globe size={12} />
                Sources: {q.research_summary.sources.join(' · ')}
                {q.research_summary.official_website && (
                  <span className="text-sky-400"> · Site: {q.research_summary.official_website}</span>
                )}
              </div>
              {q.research_summary.detailed_summary && (
                <details className="mt-4 rounded-xl border border-slate-800/60 bg-slate-900/40 p-4">
                  <summary className="cursor-pointer text-xs font-semibold text-indigo-400">
                    Full research report (Tavily + Firecrawl)
                  </summary>
                  <pre className="mt-3 whitespace-pre-wrap text-xs leading-relaxed text-slate-300">
                    {q.research_summary.detailed_summary}
                  </pre>
                </details>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="card p-6">
              <h2 className="text-sm font-semibold text-slate-300">Agent timeline</h2>
              <div className="mt-4">
                {q.timeline.map((step, i) => {
                  const Icon = AGENT_ICONS[step.agent] ?? Search
                  const done = step.status === 'done'
                  return (
                    <div key={step.agent} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${done ? 'bg-emerald-500/15 text-emerald-400' : 'bg-amber-500/15 text-amber-400'}`}>
                          <Icon size={15} />
                        </div>
                        {i < q.timeline.length - 1 && <div className="my-1 w-px flex-1 bg-slate-800" />}
                      </div>
                      <div className="pb-5">
                        <div className="text-sm font-semibold text-slate-200">
                          {step.agent.replace(/_/g, ' ')}
                        </div>
                        <div className="mt-0.5 text-xs leading-relaxed text-slate-400">{step.action}</div>
                        <div className="mt-1 flex items-center gap-1 text-[11px] text-slate-600">
                          <Clock size={10} /> {(step.duration_ms / 1000).toFixed(1)}s
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              <h3 className="mt-2 text-sm font-semibold text-slate-300">Recommended action</h3>
              <div className="mt-2 rounded-xl border border-indigo-500/25 bg-indigo-500/10 p-4">
                <div className="text-sm font-semibold text-indigo-300">{q.recommendation.action}</div>
                <ul className="mt-2 space-y-1.5 text-xs text-slate-300">
                  {q.recommendation.talking_points.map((t) => <li key={t}>• {t}</li>)}
                </ul>
              </div>
            </div>

            <div className="card p-6 xl:col-span-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-300">
                <Mail size={15} className="text-indigo-400" /> Draft follow-up email
                <span className="ml-auto text-xs font-normal">
                  {q.draft_email?.status === 'pending_approval' && <span className="text-amber-400">Awaiting your approval</span>}
                  {q.draft_email?.status === 'approved_and_sent' && <span className="text-emerald-400">Approved & sent ✓</span>}
                  {q.draft_email?.status === 'rejected' && <span className="text-rose-400">Rejected</span>}
                </span>
              </h2>

              {q.draft_email ? (
                <>
                  <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-5">
                    <div className="border-b border-slate-800 pb-3 text-sm">
                      <span className="text-slate-500">Subject: </span>
                      <span className="font-semibold text-slate-200">{q.draft_email.subject}</span>
                    </div>
                    <pre className="mt-4 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-300">
                      {q.draft_email.body}
                    </pre>
                  </div>

                  {q.draft_email.status === 'pending_approval' && (
                    <div className="mt-4 flex items-center gap-3">
                      <button
                        onClick={() => handleEmail('approve')}
                        disabled={emailBusy}
                        className="flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-400 disabled:opacity-50"
                      >
                        <CheckCircle2 size={16} /> Approve & send
                      </button>
                      <button
                        onClick={() => handleEmail('reject')}
                        disabled={emailBusy}
                        className="flex items-center gap-2 rounded-xl border border-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-300 transition hover:border-rose-500/50 hover:text-rose-400 disabled:opacity-50"
                      >
                        <XCircle size={16} /> Reject
                      </button>
                      <span className="text-[11px] text-slate-500">
                        Human-in-the-loop: nothing is sent without your approval.
                      </span>
                    </div>
                  )}
                  {q.draft_email.status === 'approved_and_sent' && q.draft_email.delivery?.to && (
                    <div className="mt-4 text-xs text-emerald-400">
                      Sent to: {q.draft_email.delivery.to}
                    </div>
                  )}
                </>
              ) : (
                <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/60 p-6 text-center text-sm text-slate-500">
                  No outreach email — this lead scored below the outreach threshold.
                  The agent recommends a nurture campaign instead.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
