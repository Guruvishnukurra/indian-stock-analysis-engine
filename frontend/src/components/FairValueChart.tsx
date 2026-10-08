import { useRef, useState } from 'react'
import type { FairValue } from '../lib/api'
import { money, pct } from '../lib/format'
import { niceTicks } from '../lib/scale'

interface Mark {
  label: string
  value: number
  kind: 'method' | 'context' | 'price' | 'base' | 'consensus' | 'band'
  detail?: string
}

// One horizontal value scale: the fair-value band (wash), the base
// estimate, each core method (filled dot), context-only methods (hollow
// dot), today's price and the analyst consensus (reference). Every mark
// has a hover/focus tooltip; the methods table carries the same values.
export function FairValueChart({
  fairValue,
  price,
  consensus,
  growthRange,
}: {
  fairValue: FairValue
  price: number
  consensus?: number | null
  growthRange?: { p10: number; p90: number } | null
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const [tip, setTip] = useState<{ x: number; y: number; mark: Mark } | null>(null)

  const width = 760
  const height = 176
  const pad = { left: 24, right: 24 }
  const axisY = 128

  const methods: Mark[] = Object.entries(fairValue.method_upsides ?? {}).map(([label, upside]) => ({
    label,
    value: price * (1 + upside / 100),
    kind: 'method',
    detail: `${pct(upside)} vs price`,
  }))

  const context: Mark[] = Object.entries(fairValue.context_methods ?? {}).map(([label, c]) => ({
    label,
    value: c.base,
    kind: 'context',
    detail: `${pct(c.upside)} vs price. Context only, not in the range`,
  }))

  const values = [
    price,
    fairValue.low ?? price,
    fairValue.high ?? price,
    ...methods.map((m) => m.value),
    ...context.map((m) => m.value),
    ...(consensus ? [consensus] : []),
  ].filter((v) => Number.isFinite(v) && v >= 0)

  const minV = Math.min(...values) * 0.9
  const maxV = Math.max(...values) * 1.08
  const x = (v: number) => pad.left + ((v - minV) / (maxV - minV || 1)) * (width - pad.left - pad.right)

  const ticks = niceTicks(minV, maxV, 5)

  const show = (event: React.PointerEvent | React.FocusEvent, mark: Mark) => {
    const box = wrap.current?.getBoundingClientRect()
    const target = (event.currentTarget as Element).getBoundingClientRect()
    if (!box) return
    setTip({ x: target.left - box.left + target.width / 2, y: target.top - box.top, mark })
  }

  const hit = (mark: Mark, cx: number, cy: number) => (
    <rect
      x={cx - 12}
      y={cy - 14}
      width={24}
      height={28}
      fill="transparent"
      tabIndex={0}
      role="img"
      aria-label={`${mark.label}: ${money(mark.value)}`}
      onPointerEnter={(e) => show(e, mark)}
      onPointerLeave={() => setTip(null)}
      onFocus={(e) => show(e, mark)}
      onBlur={() => setTip(null)}
    />
  )

  const hasBand = fairValue.available && fairValue.low != null && fairValue.high != null

  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img"
        aria-label={`Fair value range ${money(fairValue.low)} to ${money(fairValue.high)}, base ${money(fairValue.base)}, price ${money(price)}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={30} y2={axisY} stroke="var(--grid)" strokeWidth={1} />
            <text x={x(t)} y={axisY + 20} textAnchor="middle">{money(t)}</text>
          </g>
        ))}
        <line x1={pad.left} x2={width - pad.right} y1={axisY} y2={axisY} stroke="var(--axis)" strokeWidth={1} />

        {growthRange && (
          <rect x={x(Math.max(growthRange.p10, minV))} width={Math.max(x(growthRange.p90) - x(Math.max(growthRange.p10, minV)), 2)}
            y={96} height={8} rx={4} fill="var(--series-1)" opacity={0.25} />
        )}

        {hasBand && (
          <>
            <rect x={x(fairValue.low!)} width={Math.max(x(fairValue.high!) - x(fairValue.low!), 2)}
              y={62} height={22} rx={4} fill="var(--series-1-wash)" stroke="var(--series-1)" strokeWidth={1} />
            <line x1={x(fairValue.base!)} x2={x(fairValue.base!)} y1={56} y2={90} stroke="var(--series-1)" strokeWidth={2} />
            <text x={x(fairValue.base!)} y={50} textAnchor="middle" className="label-strong">
              Base {money(fairValue.base)}
            </text>
            {hit({ label: 'Fair-value range', value: fairValue.base!, kind: 'band',
              detail: `${money(fairValue.low)} to ${money(fairValue.high)}` }, x(fairValue.base!), 73)}
          </>
        )}

        {methods.map((m) => (
          <g key={m.label}>
            <circle cx={x(m.value)} cy={73} r={5} fill="var(--series-1)" stroke="var(--surface-1)" strokeWidth={2} />
            {hit(m, x(m.value), 73)}
          </g>
        ))}

        {context.map((m) => (
          <g key={m.label}>
            <circle cx={x(m.value)} cy={73} r={5} fill="var(--surface-1)" stroke="var(--text-muted)" strokeWidth={2} />
            {hit(m, x(m.value), 73)}
          </g>
        ))}

        {consensus ? (
          <g>
            <path d={`M ${x(consensus)} ${axisY - 2} l -5 -9 h 10 z`} fill="var(--text-muted)" />
            {hit({ label: 'Analyst consensus (reference only)', value: consensus, kind: 'consensus' }, x(consensus), axisY - 6)}
          </g>
        ) : null}

        <g>
          <line x1={x(price)} x2={x(price)} y1={28} y2={axisY} stroke="var(--text-primary)" strokeWidth={2} />
          <text x={x(price)} y={20} textAnchor="middle" className="label-strong">
            Price {money(price)}
          </text>
          {hit({ label: 'Current price', value: price, kind: 'price' }, x(price), 60)}
        </g>
      </svg>

      <div className="legend" aria-hidden="true">
        <span><i className="band" style={{ background: 'var(--series-1-wash)', border: '1px solid var(--series-1)' }} />Fair-value range</span>
        <span><i className="dot" style={{ background: 'var(--series-1)' }} />Valuation method</span>
        {context.length > 0 && <span><i className="dot" style={{ border: '2px solid var(--text-muted)' }} />Context only</span>}
        {growthRange && <span><i className="band" style={{ background: 'var(--series-1)', opacity: 0.25 }} />Simulated futures (10th–90th pct)</span>}
        {consensus ? <span><i className="dot" style={{ background: 'var(--text-muted)', borderRadius: 0 }} />Analyst consensus</span> : null}
        <span><i className="line" style={{ background: 'var(--text-primary)' }} />Current price</span>
      </div>

      {tip && (
        <div className="tooltip" style={{ left: Math.min(Math.max(tip.x - 80, 0), 600), top: Math.max(tip.y - 64, 0) }}>
          <div className="row"><b>{money(tip.mark.value)}</b></div>
          <div className="secondary">{tip.mark.label}</div>
          {tip.mark.detail && <div className="muted">{tip.mark.detail}</div>}
        </div>
      )}
    </div>
  )
}
