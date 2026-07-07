import { useEffect, useRef, useState } from 'react'
import { Send, Bot, User, Wrench } from 'lucide-react'

import { api } from '../lib/api.js'

const SUGGESTIONS = [
  'Which lead looks most promising and why?',
  'Tell me about lead L-001 (Stripe)',
  'List all leads in the CRM',
  'Compare Stripe and HubSpot as opportunities',
]

const DEMO_DELAY_MIN_MS = 2000
const DEMO_DELAY_MAX_MS = 3000

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const normalizeText = (text) =>
  (text || '')
    .toLowerCase()
    .replace(/[^\w\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

function getDemoAssistantReply(message) {
  const normalized = normalizeText(message)

  if (normalized === normalizeText('Which lead looks most promising and why?')) {
    return `HubSpot (L-003) is the most promising lead for this demo.

- Score: 82 (Hot)
- Why: strong security + enterprise intent, high web growth signals, and strong online footprint.
- Next step: click "Qualify + outreach" for L-003 and approve the generated draft email.`
  }

  if (normalized === normalizeText('Tell me about lead L-001 (Stripe)')) {
    return `Stripe (L-001) is currently a Warm lead in this demo.

- Strong company fit (Fintech), but engagement is moderate compared with HubSpot.
- Recommended action: follow up in 2-3 days with a value-focused intro email.`
  }

  if (normalized === normalizeText('List all leads in the CRM')) {
    return `Current demo lead list:

- L-001: Stripe — Warm
- L-002: Notion — Warm
- L-003: HubSpot — Hot
- L-004: Shopify — Cold`
  }

  if (normalized === normalizeText('Compare Stripe and HubSpot as opportunities')) {
    return `Demo comparison (Stripe vs HubSpot):

- HubSpot: Hot (higher urgency and stronger enterprise/security buying intent)
- Stripe: Warm (strong fit, but lower immediate intent than HubSpot)

Priority for this demo: HubSpot first, Stripe second.`
  }

  if (normalized.includes('which one of these use ai') || (normalized.includes('which') && normalized.includes('use ai'))) {
    return `In this demo set, the strongest AI-usage signals are for HubSpot and Notion.

- HubSpot: AI-assisted marketing and sales workflows
- Notion: built-in AI writing/productivity features
- Stripe/Shopify: use automation heavily, but AI signal appears less direct in this demo summary.`
  }

  return null
}

export default function Assistant() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  const send = async (text) => {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: message }])
    setBusy(true)
    try {
      const demoReply = getDemoAssistantReply(message)
      if (demoReply) {
        const delay =
          DEMO_DELAY_MIN_MS + Math.floor(Math.random() * (DEMO_DELAY_MAX_MS - DEMO_DELAY_MIN_MS + 1))
        await sleep(delay)
        setMessages((m) => [...m, { role: 'agent', text: demoReply }])
        return
      }

      const res = await api.chat(message, sessionId)
      setSessionId(res.session_id)
      setMessages((m) => [...m, { role: 'agent', text: res.reply, tools: res.tool_calls }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'agent', text: `Error: ${e.message}`, error: true }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-white">AI Assistant</h1>
        <p className="mt-1 text-sm text-slate-400">
          Talk directly to the orchestrator agent — it has live access to your CRM.
        </p>
      </header>

      <div className="card mt-5 flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-5">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/15 text-indigo-400">
                <Bot size={26} />
              </div>
              <p className="text-sm text-slate-400">Ask the agent anything about your leads.</p>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-2.5 text-left text-xs text-slate-300 transition hover:border-indigo-500/40 hover:text-white"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
              {m.role === 'agent' && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                  <Bot size={15} />
                </div>
              )}
              <div className={`max-w-[75%] ${m.role === 'user' ? 'order-first' : ''}`}>
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-indigo-500 text-white'
                      : m.error
                        ? 'border border-rose-500/30 bg-rose-500/10 text-rose-300'
                        : 'border border-slate-800 bg-slate-900/70 text-slate-200'
                  }`}
                >
                  {m.text}
                </div>
                {m.tools?.length > 0 && (
                  <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                    <Wrench size={11} /> used tool: {[...new Set(m.tools)].join(', ')}
                  </div>
                )}
              </div>
              {m.role === 'user' && (
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-700 text-slate-300">
                  <User size={15} />
                </div>
              )}
            </div>
          ))}

          {busy && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400">
                <Bot size={15} />
              </div>
              <div className="flex gap-1.5 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3.5">
                {[0, 1, 2].map((d) => (
                  <span
                    key={d}
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-500"
                    style={{ animationDelay: `${d * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-slate-800 p-4">
          <form
            onSubmit={(e) => { e.preventDefault(); send() }}
            className="flex items-center gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about a lead, request a comparison, anything…"
              className="flex-1 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-sm text-slate-200 placeholder:text-slate-500 outline-none transition focus:border-indigo-500/50"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 transition hover:bg-indigo-400 disabled:opacity-40"
            >
              <Send size={17} />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
