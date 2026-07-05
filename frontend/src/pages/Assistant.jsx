import { useEffect, useRef, useState } from 'react'
import { Send, Bot, User, Wrench } from 'lucide-react'

import { api } from '../lib/api.js'

const SUGGESTIONS = [
  'Which lead looks most promising and why?',
  'Tell me about lead L-001 (Stripe)',
  'List all leads in the CRM',
  'Compare Stripe and HubSpot as opportunities',
]

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
