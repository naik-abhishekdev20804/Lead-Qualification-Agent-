import { TIER_STYLES } from '../lib/api.js'

export default function TierBadge({ tier, size = 'sm' }) {
  if (!tier) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs font-medium text-slate-400">
        Unscored
      </span>
    )
  }
  const s = TIER_STYLES[tier] ?? TIER_STYLES.Cold
  const pad = size === 'lg' ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${s.border} ${s.bg} ${pad} font-semibold ${s.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {tier}
    </span>
  )
}
