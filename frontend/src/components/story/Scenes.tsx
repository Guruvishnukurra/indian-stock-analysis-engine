import { ArrowRight, CheckCircle, XCircle } from '@phosphor-icons/react'
import { useRef } from 'react'
import type { Analysis } from '../../lib/api'
import { crore, isNum, money, pct, title } from '../../lib/format'
import { useWidth } from '../../lib/useWidth'
import { StanceBadge } from '../Status'

/* Visuals for the "How it works" story. Every number comes from the
   snapshot being followed; nothing here is illustrative. */

const METHODS: [string, string][] = [
  ['dcf', 'DCF'],
  ['peer_pe', 'Peer P/E'],
  ['peer_pb', 'Peer P/B'],
  ['peer_evs', 'Peer EV/Sales'],
  ['growth_dcf', 'Growth-stage DCF'],
  ['historical_pe', 'Historical P/E'],
]

const fy = (iso: string) => `FY${String(new Date(iso).getFullYear()).slice(2)}`

/* 1. The filings: four years of revenue and net income. */
export function DataScene({ a }: { a: Analysis }) {
  const host = useRef<HTMLDivElement>(null)
  const w = useWidth(host, 520)
  const rows = (a.fundamentals_annual ?? []).filter((r) => isNum(r.Revenue)).slice(-4)
  if (!rows.length) return <p className="scene-empty">No annual statements in this snapshot.</p>
  const max = Math.max(...rows.map((r) => Math.abs(r.Revenue as number)), ...rows.map((r) => Math.abs((r.Net_Income as number) ?? 0)))
  const hasLoss = rows.some((r) => ((r.Net_Income as number) ?? 0) < 0)
  const h = 260, top = 34, base = hasLoss ? 190 : 214, span = base - top
  const group = (w - 40) / rows.length
  const bar = Math.min(34, group / 3.2)
  const y = (v: number) => base - (v / max) * span * (v >= 0 ? 1 : 0.35)

  return (
    <div ref={host} className="scene">
      <svg className="chart scene-chart" width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`Revenue and net income for ${rows.length} fiscal years`}>
        <line x1={20} x2={w - 20} y1={base} y2={base} stroke="var(--line-strong)" />
        {rows.map((r, i) => {
          const cx = 20 + group * i + group / 2
          const rev = r.Revenue as number
          const ni = (r.Net_Income as number) ?? 0
          return (
            <g key={r.date}>
              <rect x={cx - bar - 2} width={bar} y={y(rev)} height={base - y(rev)} rx={4} fill="var(--series-1)"
                className="grow-up" style={{ animationDelay: `${i * 90}ms` }} />
              <rect x={cx + 2} width={bar} y={ni >= 0 ? y(ni) : base} height={Math.max(2, Math.abs(base - y(ni)))} rx={4}
                fill={ni >= 0 ? 'var(--series-3)' : 'var(--down)'} className={ni >= 0 ? 'grow-up' : 'grow-down'}
                style={{ animationDelay: `${i * 90 + 60}ms` }} />
              <text x={cx - bar / 2 - 2} y={y(rev) - 8} textAnchor="middle">{crore(rev)}</text>
              <text x={cx} y={h - 10} textAnchor="middle" className="label-strong">{fy(r.date)}</text>
            </g>
          )
        })}
      </svg>
      <div className="scene-legend">
        <span><i style={{ background: 'var(--series-1)' }} />Revenue</span>
        <span><i style={{ background: hasLoss ? 'var(--down)' : 'var(--series-3)' }} />Net income{hasLoss ? ' (loss shown below the line)' : ''}</span>
      </div>
    </div>
  )
}

/* 2. Routing: which methods fit this business, and why the others do not. */
export function RouteScene({ a }: { a: Analysis }) {
  const p = a.company_profile
  return (
    <div className="scene">
      <div className="route-head">
        <span className="route-type">{title(p.company_type)}</span>
        <span className="route-basis">{p.classification_basis ?? 'Classified from sector and industry'}{p.classification_certainty ? `, ${p.classification_certainty.toLowerCase()} certainty` : ''}</span>
      </div>
      <ul className="route-list">
        {METHODS.map(([key, label], i) => {
          const on = p[`${key}_applicable`] === true
          const reason = p[`${key}_reason`]
          return (
            <li key={key} className={on ? 'on' : 'off'} style={{ animationDelay: `${i * 70}ms` }}>
              {on ? <CheckCircle size={18} weight="fill" aria-hidden="true" /> : <XCircle size={18} aria-hidden="true" />}
              <span className="m">{label}<span className="visually-hidden">{on ? ': applies' : ': ruled out'}</span></span>
              <span className="r">{typeof reason === 'string' ? reason : ''}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/* 3 to 5. One number line that morphs: methods, then blend, then range. */
export function ValueScene({ a, stage }: { a: Analysis; stage: 'methods' | 'blend' | 'range' }) {
  const host = useRef<HTMLDivElement>(null)
  const w = useWidth(host, 520)
  const fv = a.fair_value
  const weights = fv.weights_used ?? {}
  const rows = METHODS
    .map(([key, label]) => ({ key, label, m: a.method_results[key], weight: weights[key] ?? 0 }))
    .filter((r) => r.m?.available && isNum(r.m.base))
  if (!fv.available || !rows.length || !isNum(fv.base)) {
    return <p className="scene-empty">{fv.reason ?? 'No fair value could be produced for this company.'}</p>
  }

  const values = [a.current_price, fv.low ?? fv.base, fv.high ?? fv.base, ...rows.flatMap((r) => [r.m.low ?? r.m.base!, r.m.high ?? r.m.base!])]
  const lo = Math.min(...values) * 0.92
  const hi = Math.max(...values) * 1.05
  const left = 18, right = 64
  const x = (v: number) => left + ((v - lo) / (hi - lo)) * (w - left - right)
  const rowY = (i: number) => 64 + i * 50
  const resultY = rowY(rows.length) + 34
  const h = resultY + 74

  return (
    <div ref={host} className="scene">
      <svg className={`chart scene-chart vl stage-${stage}`} width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img"
        aria-label={`Valuation methods for ${a.company_name}, blended into a fair value of ${money(fv.base)}`}>
        <line x1={x(a.current_price)} x2={x(a.current_price)} y1={30} y2={h - 26} stroke="var(--ink)" strokeWidth={1.5} strokeDasharray="4 4" />
        <text x={x(a.current_price)} y={20} textAnchor="middle" className="label-strong">Price {money(a.current_price)}</text>

        <g className="rows">
          {rows.map((r, i) => {
            const core = r.weight > 0
            const color = core ? 'var(--series-1)' : 'var(--ink-3)'
            return (
              <g key={r.key}>
                <text x={x(r.m.low ?? r.m.base!)} y={rowY(i) - 12} className="label-strong">{r.label}{core ? '' : ' (context only)'}</text>
                <line x1={x(r.m.low ?? r.m.base!)} x2={x(r.m.high ?? r.m.base!)} y1={rowY(i)} y2={rowY(i)} stroke={color} strokeWidth={3} strokeLinecap="round" opacity={0.45} />
                <circle cx={x(r.m.base!)} cy={rowY(i)} r={6} fill={core ? color : 'var(--surface)'} stroke={color} strokeWidth={2} />
                {Math.abs(x(r.m.base!) - x(a.current_price)) < 48
                  ? <text x={x(r.m.base!) - 10} y={rowY(i) + 18} textAnchor="end">{money(r.m.base)}</text>
                  : <text x={x(r.m.base!) + 10} y={rowY(i) + 18}>{money(r.m.base)}</text>}
                {core && <text className="weights" x={w - right + 10} y={rowY(i) + 4}>{Math.round(r.weight * 100)}%</text>}
                {core && <line className="links" x1={x(r.m.base!)} y1={rowY(i) + 6} x2={x(fv.base!)} y2={resultY - 8} stroke={color} strokeWidth={1.5} strokeDasharray="3 4" />}
              </g>
            )
          })}
        </g>

        <g className="band">
          <rect x={x(fv.low ?? fv.base)} width={Math.max(4, x(fv.high ?? fv.base) - x(fv.low ?? fv.base))} y={resultY - 14} height={28} rx={6}
            fill="var(--series-1-wash)" stroke="var(--series-1)" />
          <text x={x(fv.low ?? fv.base)} y={resultY + 34}>{money(fv.low)}</text>
          <text x={x(fv.high ?? fv.base)} y={resultY + 34} textAnchor="end">{money(fv.high)}</text>
        </g>
        <g className="result">
          <line x1={x(fv.base)} x2={x(fv.base)} y1={resultY - 18} y2={resultY + 18} stroke="var(--series-1)" strokeWidth={3} />
          <text x={x(fv.base)} y={resultY + 52} textAnchor="middle" className="label-strong">Base {money(fv.base)}</text>
        </g>
      </svg>
      <p className="scene-caption" aria-live="polite">
        {stage === 'methods' && `${rows.filter((r) => r.weight > 0).length} core method${rows.filter((r) => r.weight > 0).length === 1 ? '' : 's'}, each with its own low, base and high value.`}
        {stage === 'blend' && `Weighted blend: ${rows.filter((r) => r.weight > 0).map((r) => `${Math.round(r.weight * 100)}% ${r.label}`).join(' + ')} = ${money(fv.base)}.`}
        {stage === 'range' && `Range ${money(fv.low)} to ${money(fv.high)}. The base sits ${pct(fv.upside_base, true, 0)} from today's price.`}
      </p>
    </div>
  )
}

/* 6. Confidence: points per check. */
export function ConfidenceScene({ a }: { a: Analysis }) {
  const parts = a.confidence.components ?? []
  return (
    <div className="scene">
      <ul className="conf-list">
        {parts.map((c, i) => {
          const share = c.max ? c.points / c.max : 0
          return (
            <li key={c.name}>
              <span className="n">{c.name}</span>
              <span className={`meter ${share >= 0.75 ? 'good' : share >= 0.45 ? 'warn' : 'bad'}`} aria-hidden="true">
                <span style={{ width: `${Math.max(3, share * 100)}%`, animationDelay: `${i * 80}ms` }} />
              </span>
              <span className="p">{Math.round(c.points)}/{c.max}</span>
            </li>
          )
        })}
      </ul>
      <div className="conf-total"><span className="big">{a.confidence.score}</span><span>/100, {a.confidence.label.toLowerCase()} confidence</span></div>
    </div>
  )
}

/* 7. The verdict: three separate judgements, then the stance. */
export function VerdictScene({ a }: { a: Analysis }) {
  const v = a.explanation.verdicts
  const parts = [
    ['Quality', v?.quality ?? a.fundamental_score.label],
    ['Valuation', v?.valuation.label ?? 'n/a'],
    ['Timing', v?.timing.label ?? a.technical_score.label],
  ]
  return (
    <div className="scene">
      <ol className="verdict-row">
        {parts.map(([k, val], i) => (
          <li key={k} style={{ animationDelay: `${i * 110}ms` }}><span className="k">{k}</span><span className="v">{val}</span></li>
        ))}
        <li className="arrow" aria-hidden="true"><ArrowRight size={18} /></li>
        <li className="stance-cell"><span className="k">Stance</span><StanceBadge stance={a.explanation.stance} /></li>
      </ol>
      {a.conclusion && <p className="verdict-text">{a.conclusion}</p>}
    </div>
  )
}
