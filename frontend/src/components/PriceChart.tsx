import { useMemo, useRef, useState } from 'react'
import type { Analysis } from '../lib/api'
import { dateLabel, money } from '../lib/format'
import { niceTicks } from '../lib/scale'
import { useWidth } from '../lib/useWidth'

const SERIES = [
  { key: 'Close', label: 'Price', color: 'var(--series-1)' },
  { key: 'SMA_50', label: '50-day average', color: 'var(--series-2)' },
  { key: 'SMA_200', label: '200-day average', color: 'var(--series-3)' },
] as const

type Row = Analysis['price_history'][number]

const height = 260
const pad = { left: 56, right: 92, top: 12, bottom: 28 }

// About one year of closing prices with 50/200-day averages.
// Crosshair snaps to the nearest day; one tooltip lists every series.
export function PriceChart({ data }: { data: Row[] }) {
  const wrap = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const width = useWidth(wrap)

  const { x, y, paths, yTicks, xTicks } = useMemo(() => {
    const values = data.flatMap((r) => SERIES.map((s) => r[s.key])).filter((v): v is number => v != null)
    const lo = Math.min(...values) * 0.97
    const hi = Math.max(...values) * 1.02
    const x = (i: number) => pad.left + (i / Math.max(data.length - 1, 1)) * (width - pad.left - pad.right)
    const y = (v: number) => pad.top + (1 - (v - lo) / (hi - lo || 1)) * (height - pad.top - pad.bottom)

    const paths = SERIES.map((s) => {
      let d = ''
      let pen = false
      data.forEach((r, i) => {
        const v = r[s.key]
        if (v == null) { pen = false; return }
        d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`
        pen = true
      })
      return d
    })

    const step = Math.max(Math.floor(data.length / 5), 1)
    const xTicks = data.map((_, i) => i).filter((i) => i % step === 0)

    return { x, y, paths, yTicks: niceTicks(lo, hi, 5), xTicks }
  }, [data, width])

  if (data.length < 2) return <p className="muted">Not enough price history to chart.</p>

  const onMove = (event: React.PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect()
    const fraction = (event.clientX - box.left) / box.width
    setHover(Math.min(data.length - 1, Math.max(0, Math.round(fraction * (data.length - 1)))))
  }

  const last = data[data.length - 1]
  const hovered = hover != null ? data[hover] : null

  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <svg className="chart" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img"
        aria-label={`Price over the last year, latest ${money(last.Close)}`}>
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} stroke="var(--line)" strokeWidth={1} />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end">{money(t)}</text>
          </g>
        ))}
        {xTicks.map((i) => (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle">
            {new Date(data[i].date).toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })}
          </text>
        ))}

        {SERIES.map((s, index) => (
          <path key={s.key} d={paths[index]} fill="none" stroke={s.color} strokeWidth={2}
            strokeLinejoin="round" strokeLinecap="round" />
        ))}

        {/* Direct end labels (relief for the low-contrast aqua line). */}
        {SERIES.map((s, index) => {
          const value = last[s.key]
          if (value == null) return null
          return (
            <g key={s.key}>
              <circle cx={x(data.length - 1)} cy={y(value)} r={4} fill={s.color} stroke="var(--surface)" strokeWidth={2} />
              <text x={x(data.length - 1) + 8} y={y(value) + 4 + (index - 1) * 2}>{index === 0 ? money(value) : s.label.split(' ')[0]}</text>
            </g>
          )
        })}

        {hovered && hover != null && (
          <line x1={x(hover)} x2={x(hover)} y1={pad.top} y2={height - pad.bottom} stroke="var(--line-strong)" strokeWidth={1} />
        )}

        <rect x={pad.left} y={pad.top} width={width - pad.left - pad.right} height={height - pad.top - pad.bottom}
          fill="transparent" onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>

      <div className="legend">
        {SERIES.map((s) => (
          <span key={s.key}><i className="line" style={{ background: s.color }} />{s.label}</span>
        ))}
      </div>

      {hovered && hover != null && (
        <div className="tooltip" style={{ left: `${Math.min((x(hover) / width) * 100, 70)}%`, top: 8 }}>
          <div className="muted">{dateLabel(hovered.date)}</div>
          {SERIES.map((s) => (
            <div className="row" key={s.key}>
              <span className="secondary"><span className="key" style={{ background: s.color }} /> {s.label}</span>
              <b>{money(hovered[s.key])}</b>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
