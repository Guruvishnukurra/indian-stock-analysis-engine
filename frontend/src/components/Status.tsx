import type { Stance } from '../lib/api'

// Status colors are reserved for state and always ship with an icon and a
// text label - never color alone.
const STANCE: Record<Stance, { color: string; icon: string }> = {
  ATTRACTIVE: { color: 'var(--good)', icon: '✓' },
  WATCH: { color: 'var(--warning)', icon: '!' },
  AVOID: { color: 'var(--critical)', icon: '✕' },
  'NOT RATED': { color: 'var(--neutral-status)', icon: '–' },
  'INSUFFICIENT DATA': { color: 'var(--neutral-status)', icon: '?' },
}

export function StanceBadge({ stance }: { stance: Stance }) {
  const style = STANCE[stance] ?? STANCE['NOT RATED']
  return (
    <span className="status">
      <span className="dot" style={{ background: style.color }} aria-hidden="true">
        {style.icon}
      </span>
      {stance}
    </span>
  )
}

const ASSESSMENT: Record<string, string> = {
  Strong: 'var(--good)',
  Moderate: 'var(--warning)',
  Weak: 'var(--critical)',
}

export function AssessmentPill({ label }: { label: string }) {
  return (
    <span className="pill">
      <i style={{ background: ASSESSMENT[label] ?? 'var(--neutral-status)' }} aria-hidden="true" />
      {label}
    </span>
  )
}
