import { CheckCircle, MinusCircle, Question, WarningCircle, XCircle } from '@phosphor-icons/react'
import type { Stance } from '../lib/api'

// Status colors are reserved for state and always ship with an icon and
// a text label - never color alone.
const STANCE: Record<Stance, { tone: string; Icon: typeof CheckCircle }> = {
  ATTRACTIVE: { tone: 'good', Icon: CheckCircle },
  WATCH: { tone: 'warn', Icon: WarningCircle },
  AVOID: { tone: 'bad', Icon: XCircle },
  'NOT RATED': { tone: 'neutral', Icon: MinusCircle },
  'INSUFFICIENT DATA': { tone: 'neutral', Icon: Question },
}

const LABEL: Record<Stance, string> = {
  ATTRACTIVE: 'Attractive',
  WATCH: 'Watch',
  AVOID: 'Avoid',
  'NOT RATED': 'Not rated',
  'INSUFFICIENT DATA': 'Insufficient data',
}

export function StanceBadge({ stance }: { stance: Stance }) {
  const { tone, Icon } = STANCE[stance] ?? STANCE['NOT RATED']
  return (
    <span className={`stance ${tone}`}>
      <Icon size={18} weight="fill" aria-hidden="true" />
      {LABEL[stance] ?? stance}
    </span>
  )
}
