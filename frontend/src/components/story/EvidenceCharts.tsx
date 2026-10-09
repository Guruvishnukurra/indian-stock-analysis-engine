import { useRef, useState } from 'react'
import { Link } from 'react-router'
import type { ConsensusRow, ErrorRow, GoldenRow, MlTrend, NewsEval } from '../../lib/evidence'
import { typicalMiss } from '../../lib/evidence'
import { title } from '../../lib/format'
import { useWidth } from '../../lib/useWidth'
import { StanceBadge } from '../Status'
import type { Stance } from '../../lib/api'
import { SlideIndicator } from '../../motion/SlideIndicator'

const pc = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`
const sentence = (t: string) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase()
const ACRONYMS: Record<string, string> = { nbfc: 'NBFC', capital_markets: 'Capital markets', asset_management: 'Asset management', healthcare_services: 'Healthcare services', real_estate: 'Real estate', consumer_cyclical: 'Consumer cyclical', consumer_defensive: 'Consumer defensive' }
const typeName = (k: string) => ACRONYMS[k] ?? sentence(k.replace(/_/g, ' '))

/* ML trend: balanced accuracy per test year, best model vs the gate. */
export function MlChart({ ml }: { ml: MlTrend }) {
  const host = useRef<HTMLDivElement>(null)
  const w = useWidth(host, 640)
  const [hover, setHover] = useState<number | null>(null)
  const years = ml.per_year
  const baseline = ml.summary[ml.gate.best_baseline]?.balanced_accuracy ?? 1 / 3
  const gate = baseline + ml.gate.required_edge
  const series = [
    { key: 'logistic' as const, label: 'Logistic regression (best model)', color: 'var(--series-1)' },
    { key: 'gradient_boosting' as const, label: 'Gradient boosting', color: 'var(--series-2)' },
  ]
  const narrow = w < 560
  const h = 280, pad = { l: 44, r: narrow ? 96 : 150, t: 20, b: 34 }
  const lo = 0.28, hi = 0.44
  const x = (i: number) => pad.l + (i / (years.length - 1)) * (w - pad.l - pad.r)
  const y = (v: number) => pad.t + (1 - (v - lo) / (hi - lo)) * (h - pad.t - pad.b)
  const ticks = [0.3, 0.35, 0.4]

  return (
    <div ref={host} className="ev-chart">
      <svg className="chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`Walk-forward balanced accuracy by year. Best model ${pc(ml.summary[ml.gate.best_model].balanced_accuracy, 1)} overall against a ${pc(baseline, 1)} baseline; ${pc(gate, 1)} was required.`}
        onPointerLeave={() => setHover(null)}
        onPointerMove={(e) => {
          const box = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          const i = Math.round(((e.clientX - box.left - pad.l) / (w - pad.l - pad.r)) * (years.length - 1))
          setHover(i >= 0 && i < years.length ? i : null)
        }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--line)" />
            <text x={pad.l - 8} y={y(t) + 4} textAnchor="end">{pc(t)}</text>
          </g>
        ))}
        {years.map((r, i) => <text key={r.year} x={x(i)} y={h - 10} textAnchor="middle">{narrow ? `'${String(r.year).slice(2)}` : r.year}</text>)}

        <rect x={pad.l} width={w - pad.l - pad.r} y={y(hi)} height={y(gate) - y(hi)} fill="var(--up-soft)" />
        <line x1={pad.l} x2={w - pad.r} y1={y(gate)} y2={y(gate)} stroke="var(--ink)" strokeDasharray="6 5" />
        <text x={w - pad.r + 8} y={y(gate) + 4} className="label-strong">{narrow ? 'Needed' : 'Needed to show it'}</text>
        <text x={w - pad.r + 8} y={y(gate) + 18}>{pc(gate, 1)}</text>
        <line x1={pad.l} x2={w - pad.r} y1={y(baseline)} y2={y(baseline)} stroke="var(--ink-3)" strokeWidth={2} />
        <text x={w - pad.r + 8} y={y(baseline) + 4}>{narrow ? 'Baseline' : 'Always guess the'}</text>
        <text x={w - pad.r + 8} y={y(baseline) + 18}>{narrow ? pc(baseline, 1) : `majority: ${pc(baseline, 1)}`}</text>

        {series.map((s, si) => (
          <g key={s.key}>
            <path d={years.map((r, i) => `${i ? 'L' : 'M'}${x(i)},${y(r[s.key])}`).join('')} fill="none" stroke={s.color}
              strokeWidth={2} strokeLinejoin="round" pathLength={1} className="draw-in" style={{ animationDelay: `${si * 200}ms` }} />
            {years.map((r, i) => <circle key={r.year} cx={x(i)} cy={y(r[s.key])} r={hover === i ? 5 : 3.5} fill={s.color} stroke="var(--surface)" strokeWidth={2} />)}
          </g>
        ))}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={h - pad.b} stroke="var(--line-strong)" />}
      </svg>
      {hover != null && (
        <div className="tooltip" style={{ left: Math.min(x(hover) + 12, w - 220), top: 12 }}>
          <strong>{years[hover].year} test year ({years[hover].n_test.toLocaleString('en-IN')} samples)</strong>
          {series.map((s) => (
            <div key={s.key} className="row"><span><i className="key" style={{ background: s.color }} /> {s.label.split(' (')[0]}</span><b>{pc(years[hover][s.key], 1)}</b></div>
          ))}
          <div className="row"><span>Baseline</span><b>{pc(baseline, 1)}</b></div>
        </div>
      )}
      <div className="legend">
        {series.map((s) => <span key={s.key}><i className="key" style={{ background: s.color }} />{s.label}</span>)}
      </div>
    </div>
  )
}

/* Horizontal bars with direct value labels. */
function Bars({ rows, max = 1, format = (v: number) => pc(v) }: {
  rows: { label: string; value: number; color: string; strong?: boolean; note?: string }[]
  max?: number
  format?: (v: number) => string
}) {
  return (
    <ul className="ev-bars">
      {rows.map((r, i) => (
        <li key={r.label} className={r.strong ? 'strong' : ''}>
          <span className="lbl">{r.label}{r.note && <small>{r.note}</small>}</span>
          <span className="track">
            <span className="fill" style={{ width: `${Math.max(1.5, (r.value / max) * 100)}%`, background: r.color, animationDelay: `${i * 60}ms` }} />
          </span>
          <span className="val">{format(r.value)}</span>
        </li>
      ))}
    </ul>
  )
}

export function MlSummary({ ml }: { ml: MlTrend }) {
  const names: Record<string, string> = {
    majority: 'Majority baseline', momentum: 'Momentum rule', technical: 'Technical score',
    logistic: 'Logistic regression', gradient_boosting: 'Gradient boosting',
  }
  const rows = Object.entries(ml.summary)
    .sort((a, b) => b[1].balanced_accuracy - a[1].balanced_accuracy)
    .map(([k, v]) => ({ label: names[k] ?? title(k), value: v.balanced_accuracy, color: k === ml.gate.best_model ? 'var(--series-1)' : 'var(--ink-3)', strong: k === ml.gate.best_model }))
  return <Bars rows={rows} max={0.45} format={(v) => pc(v, 1)} />
}

const APPROACHES: { key: 'keyword_baseline' | 'llm' | 'llm_verified'; label: string; color: string }[] = [
  { key: 'keyword_baseline', label: 'Keyword rules', color: 'var(--ink-3)' },
  { key: 'llm', label: 'Local AI, one pass', color: 'var(--series-2)' },
  { key: 'llm_verified', label: 'Local AI + verification pass', color: 'var(--series-1)' },
]

export function NewsBars({ test }: { test: NewsEval }) {
  const metrics: { key: 'material_precision' | 'reported_exact_type_precision' | 'material_recall'; label: string }[] = [
    { key: 'material_precision', label: 'Reported events that are genuine' },
    { key: 'reported_exact_type_precision', label: 'Reported with the exact event type' },
    { key: 'material_recall', label: 'Real events that get reported' },
  ]
  return (
    <div className="ev-groups">
      {metrics.map((m) => (
        <div key={m.key} className="ev-group">
          <h3>{m.label}</h3>
          <Bars rows={APPROACHES.map((a) => ({ label: a.label, value: test[a.key][m.key], color: a.color, strong: a.key === 'llm_verified' }))} />
        </div>
      ))}
    </div>
  )
}

const PEER_NAMES: Record<string, string> = {
  market_cap: 'Largest companies in the sector',
  ownership: 'Same ownership (PSU or private)',
  similarity: 'Business-description similarity',
  'ownership+similarity': 'Ownership + similarity',
  hybrid: 'Hybrid score',
  'floor_0.02': '+ 2% size floor',
  'floor_0.05': '+ 5% size floor',
  'floor_0.10': '+ 10% size floor',
  'floor_0.20': '+ 20% size floor',
}

export function PeerBars({ rows, used = 'floor_0.20' }: { rows: Record<string, ErrorRow>; used?: string }) {
  const list = Object.entries(rows).map(([k, v]) => ({
    label: PEER_NAMES[k] ?? k, value: typicalMiss(v.median_abs_log_error),
    color: k === used ? 'var(--series-1)' : 'var(--ink-3)', strong: k === used, note: k === used ? 'used by the engine' : undefined,
  }))
  const max = Math.max(...list.map((r) => r.value)) * 1.1
  return <Bars rows={list} max={max} />
}

export function ConsensusRows({ rows }: { rows: Record<string, ConsensusRow> }) {
  const list = Object.entries(rows).sort((a, b) => a[1].median_engine_vs_consensus - b[1].median_engine_vs_consensus)
  const span = Math.max(...list.map(([, r]) => Math.abs(r.median_engine_vs_consensus))) * 1.1
  return (
    <div className="table-wrap">
      <table className="ev-table">
        <thead>
          <tr><th>Company type</th><th className="num">Companies</th><th>Engine vs consensus (median)</th><th className="num">Consensus inside range</th></tr>
        </thead>
        <tbody>
          {list.map(([k, r]) => {
            const v = r.median_engine_vs_consensus
            const width = (Math.abs(v) / span) * 50
            return (
              <tr key={k}>
                <td>{typeName(k)}</td>
                <td className="num">{r.companies}</td>
                <td>
                  <span className="diverge" aria-hidden="true">
                    <span className="mid" />
                    <span className="bar" style={{ left: v < 0 ? `${50 - width}%` : '50%', width: `${width}%`, background: v < 0 ? 'var(--series-2)' : 'var(--series-1)' }} />
                  </span>
                  <span className="mono small">{v > 0 ? '+' : ''}{pc(v)}</span>
                </td>
                <td className="num">{pc(r.consensus_inside_engine_range)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const STANCE_FILTERS = ['All', 'ATTRACTIVE', 'WATCH', 'AVOID', 'NOT RATED'] as const

export function GoldenGrid({ golden }: { golden: Record<string, GoldenRow> }) {
  const [filter, setFilter] = useState<(typeof STANCE_FILTERS)[number]>('All')
  const groups = new Map<string, [string, GoldenRow][]>()
  for (const [t, r] of Object.entries(golden)) {
    if (filter !== 'All' && r.stance !== filter) continue
    const k = r.company_type ?? 'unclassified'
    groups.set(k, [...(groups.get(k) ?? []), [t, r]])
  }
  const counts = Object.fromEntries(STANCE_FILTERS.map((f) => [f, Object.values(golden).filter((r) => f === 'All' || r.stance === f).length]))
  return (
    <div className="golden">
      <div className="seg" role="radiogroup" aria-label="Filter by stance">
        <SlideIndicator index={STANCE_FILTERS.indexOf(filter)} className="seg-pill" kind="pill" />
        {STANCE_FILTERS.map((f) => (
          <button key={f} type="button" role="radio" aria-checked={filter === f} onClick={() => setFilter(f)}>
            {f === 'All' ? 'All' : sentence(f)}<span className="count">{counts[f]}</span>
          </button>
        ))}
      </div>
      <div className="golden-groups">
        {[...groups.entries()].sort((a, b) => b[1].length - a[1].length).map(([type, items]) => (
          <section key={type} className="golden-group">
            <h3>{typeName(type)}</h3>
            <ul>
              {items.map(([ticker, r]) => (
                <li key={ticker}>
                  <Link to={`/s/${ticker.replace(/\.(NS|BO)$/, '')}`} className="golden-chip">
                    <span className="sym">{ticker.replace(/\.(NS|BO)$/, '')}</span>
                    {r.stance && <StanceBadge stance={r.stance as Stance} />}
                    <span className="methods">{(r.methods ?? []).join(', ') || 'No fair value'}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
}
