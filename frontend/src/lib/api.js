const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const raw = await res.text().catch(() => '')
    let message = `Request failed (${res.status})`
    if (raw) {
      try {
        const parsed = JSON.parse(raw)
        message = parsed.detail || parsed.message || message
      } catch {
        message = raw.trim() || message
      }
    }
    throw new Error(message)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),
  leads: () => request('/leads'),
  leadDetail: (id) => request(`/leads/${id}`),
  emailAction: (id, action) =>
    request(`/leads/${id}/email`, { method: 'POST', body: JSON.stringify({ action }) }),
  runResearch: (id) => request(`/leads/${id}/research`, { method: 'POST' }),
  qualifyLead: (id) => request(`/leads/${id}/qualify`, { method: 'POST' }),
  runOutreach: (id) => request(`/leads/${id}/outreach`, { method: 'POST' }),
  chat: (message, sessionId) =>
    request('/chat', { method: 'POST', body: JSON.stringify({ message, session_id: sessionId }) }),
  budget: () => request('/budget'),
}

export const TIER_STYLES = {
  Hot: { text: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30', dot: 'bg-rose-400', chart: '#fb7185' },
  Warm: { text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30', dot: 'bg-amber-400', chart: '#fbbf24' },
  Cold: { text: 'text-sky-400', bg: 'bg-sky-500/10', border: 'border-sky-500/30', dot: 'bg-sky-400', chart: '#38bdf8' },
}
