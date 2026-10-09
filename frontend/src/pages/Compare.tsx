import { ArrowsLeftRight, Lightning } from '@phosphor-icons/react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { AppHeader } from '../components/AppHeader'
import { StanceBadge } from '../components/Status'
import { CountUp } from '../motion/CountUp'
import type { Analysis } from '../lib/api'
import { DISCLAIMER } from '../lib/copy'
import { type DemoItem, bareSymbol, getManifest } from '../lib/demo'
import { isNum, metricValue, money, title } from '../lib/format'
import { useAnalysis, type AnalysisState } from '../lib/useAnalysis'

const TICKER = /^[A-Z0-9&-]{1,20}$/

function Slot({ id, label, value, items, onChange }: {
  id: string; label: string; value: string; items: DemoItem[]; onChange: (t: string) => void
}) {
  const [draft, setDraft] = useState(value)
  const commit = () => {
    const clean = bareSymbol(draft)
    if (TICKER.test(clean) && clean !== value) onChange(clean)
    else setDraft(value)
  }
  return (
    <form className="cmp-slot" onSubmit={(e) => { e.preventDefault(); commit() }}>
      <label htmlFor={id}>{label}</label>
      <input id={id} list="cmp-companies" value={draft} onChange={(e) => setDraft(e.target.value.toUpperCase())}
        onBlur={commit} autoComplete="off" spellCheck={false} />
      <datalist id="cmp-companies">{items.map((i) => <option key={i.symbol} value={i.symbol}>{i.description}</option>)}</datalist>
    </form>
  )
}

function Column({ state, symbol }: { state: AnalysisState; symbol: string }) {
  const a = state.analysis
  if (state.status === 'error') return <div className="cmp-col error">Could not analyse {symbol}: {state.error}</div>
  if (!a) return <div className="cmp-col"><span className="pulse" aria-hidden="true" /> Analysing {symbol}{state.job?.status === 'running' ? ' with the live engine' : ''}</div>
  return (
    <div className="cmp-col">
      <Link className="cmp-name" to={`/s/${symbol}`}>{a.company_name}</Link>
      <div className="cmp-meta">
        <span className="tag mono">{symbol}</span>
        <span className="tag">{title(a.company_profile.company_type).toLowerCase()}</span>
        {state.source?.kind === 'live' && <span className="tag live"><Lightning size={12} weight="fill" aria-hidden="true" />Live</span>}
      </div>
      <div className="cmp-price"><span className="mono">{money(a.current_price)}</span><StanceBadge stance={a.explanation.stance} /></div>
    </div>
  )
}

/* Each company's fair-value range as a % of its own price, on one axis. */
function RangeCompare({ a, b }: { a: Analysis; b: Analysis }) {
  const rows = [a, b].map((x) => {
    const fv = x.fair_value
    const rel = (v?: number) => (isNum(v) ? (v / x.current_price - 1) * 100 : null)
    return { x, low: rel(fv.low), base: rel(fv.base), high: rel(fv.high) }
  })
  const vals = rows.flatMap((r) => [r.low, r.high, r.base]).filter(isNum)
  const lo = Math.min(-20, ...vals) - 5
  const hi = Math.max(20, ...vals) + 5
  const at = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`
  return (
    <div className="rc">
      <div className="rc-axis" aria-hidden="true">
        <span style={{ left: at(0) }} className="rc-zero">Today's price</span>
      </div>
      {rows.map(({ x, low, base, high }, i) => (
        <div key={i} className="rc-row">
          <span className="rc-label">{bareSymbol(x.ticker)}</span>
          <div className="rc-track">
            <span className="rc-price" style={{ left: at(0) }} aria-hidden="true" />
            {isNum(low) && isNum(high) && isNum(base) ? (
              <>
                <span className={`rc-band s${i}`} style={{ clipPath: `inset(0 calc(100% - ${at(high)}) 0 ${at(low)} round 7px)` }} />
                <span className={`rc-base s${i}`} style={{ left: at(base) }} />
                <span className="rc-val" style={{ left: at(base) }}>
                  {base >= 0 ? '+' : ''}<CountUp value={base} format={(n) => `${n.toFixed(0)}%`} /> to base
                </span>
              </>
            ) : <span className="rc-none">{x.fair_value.reason ?? 'No fair value'}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

/* Mirrored bars: A grows left, B grows right, from a shared spine. */
function Butterfly({ rows }: { rows: { label: string; a: number | null; b: number | null; aText?: string; bText?: string }[] }) {
  return (
    <ul className="bf">
      {rows.map((r) => {
        const win = isNum(r.a) && isNum(r.b) ? (r.a > r.b ? 'a' : r.b > r.a ? 'b' : '') : ''
        return (
          <li key={r.label}>
            <span className={`bf-val left${win === 'a' ? ' win' : ''}`}>{r.aText ?? (isNum(r.a) ? Math.round(r.a) : 'n/a')}</span>
            <span className="bf-bar left" aria-hidden="true"><span style={{ transform: `scaleX(${isNum(r.a) ? Math.max(0.02, r.a / 100) : 0})` }} /></span>
            <span className="bf-label">{r.label}</span>
            <span className="bf-bar right" aria-hidden="true"><span style={{ transform: `scaleX(${isNum(r.b) ? Math.max(0.02, r.b / 100) : 0})` }} /></span>
            <span className={`bf-val right${win === 'b' ? ' win' : ''}`}>{r.bText ?? (isNum(r.b) ? Math.round(r.b) : 'n/a')}</span>
          </li>
        )
      })}
    </ul>
  )
}

function Card({ title: heading, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <section className="card cmp-card">
      <div className="card-head"><h2 className="card-title">{heading}</h2>{note && <span className="muted small">{note}</span>}</div>
      {children}
    </section>
  )
}

function differences(a: Analysis, b: Analysis) {
  const rows: { label: string; gap: number; leader: string }[] = []
  const push = (label: string, x: number | null | undefined, y: number | null | undefined) => {
    if (isNum(x) && isNum(y) && Math.abs(x - y) >= 1) rows.push({ label, gap: Math.abs(x - y), leader: x > y ? bareSymbol(a.ticker) : bareSymbol(b.ticker) })
  }
  push('quality', a.fundamental_score.score, b.fundamental_score.score)
  push('confidence', a.confidence.score, b.confidence.score)
  for (const m of a.fundamental_score.metrics) {
    const other = b.fundamental_score.metrics.find((x) => x.key === m.key)
    // lowercase the first word unless it is an acronym (EPS, FCF)
    push(/^[A-Z]{2}/.test(m.label) ? m.label : m.label.charAt(0).toLowerCase() + m.label.slice(1), m.score, other?.score)
  }
  return rows.sort((x, y) => y.gap - x.gap).slice(0, 3)
}

export function ComparePage() {
  const [params, setParams] = useSearchParams()
  const a = bareSymbol(params.get('a') ?? 'TCS') || 'TCS'
  const b = bareSymbol(params.get('b') ?? 'INFY') || 'INFY'
  const [items, setItems] = useState<DemoItem[]>([])
  const sa = useAnalysis(a, false, 0)
  const sb = useAnalysis(b, false, 0)

  useEffect(() => { getManifest().then((m) => setItems(m.items)) }, [])

  const set = (key: 'a' | 'b', value: string) => setParams((p) => { p.set(key, value); return p }, { replace: true })
  const swap = () => setParams({ a: b, b: a }, { replace: true })
  const A = sa.analysis, B = sb.analysis

  const shared = A && B ? A.fundamental_score.metrics
    .map((m) => ({ m, o: B.fundamental_score.metrics.find((x) => x.key === m.key) }))
    .filter((r) => r.o) : []

  return (
    <>
      <a className="skip-link" href="#content">Skip to content</a>
      <AppHeader />
      <div className="shell">
        <main id="content" tabIndex={-1} className="cmp">
          <header className="cmp-head">
            <h1>Compare two companies</h1>
            <div className="cmp-pickers">
              <Slot key={`a-${a}`} id="cmp-a" label="First company" value={a} items={items} onChange={(t) => set('a', t)} />
              <button type="button" className="btn btn-secondary btn-icon cmp-swap" onClick={swap} aria-label={`Swap ${a} and ${b}`} title="Swap">
                <ArrowsLeftRight size={18} />
              </button>
              <Slot key={`b-${b}`} id="cmp-b" label="Second company" value={b} items={items} onChange={(t) => set('b', t)} />
            </div>
          </header>

          <div className="cmp-cols">
            <Column state={sa} symbol={a} />
            <span className="cmp-vs" aria-hidden="true">vs</span>
            <Column state={sb} symbol={b} />
          </div>

          {A && B && (
            <div className="stack">
              {differences(A, B).length > 0 && (
                <section className="bottom-line" aria-labelledby="cmp-diff-h">
                  <h2 id="cmp-diff-h" className="cmp-diff-h">Biggest differences</h2>
                  <ul className="cmp-diffs">
                    {differences(A, B).map((d) => (
                      <li key={d.label}><b>{d.leader}</b> scores {Math.round(d.gap)} points higher on {d.label}.</li>
                    ))}
                  </ul>
                </section>
              )}

              <Card title="Fair value relative to today's price" note="Each range is measured against its own share price">
                <RangeCompare a={A} b={B} />
              </Card>

              <Card title="Scores" note="0 to 100; the higher score in each row is highlighted">
                <div className="bf-heads" aria-hidden="true"><span>{a}</span><span /><span>{b}</span></div>
                <Butterfly rows={[
                  { label: 'Confidence', a: A.confidence.score, b: B.confidence.score },
                  { label: 'Quality', a: A.fundamental_score.score, b: B.fundamental_score.score },
                  ...shared.map(({ m, o }) => ({
                    label: m.label, a: m.score, b: o!.score,
                    aText: metricValue(m.value, m.unit), bText: metricValue(o!.value, o!.unit),
                  })),
                ]} />
              </Card>

              <Card title="Verdicts and methods">
                <div className="table-wrap">
                  <table className="cmp-table">
                    <thead><tr><th /><th>{a}</th><th>{b}</th></tr></thead>
                    <tbody>
                      {([
                        ['Stance', <StanceBadge key="sa" stance={A.explanation.stance} />, <StanceBadge key="sb" stance={B.explanation.stance} />],
                        ['Quality', A.explanation.verdicts?.quality ?? A.fundamental_score.label, B.explanation.verdicts?.quality ?? B.fundamental_score.label],
                        ['Valuation', A.explanation.verdicts?.valuation.label ?? 'n/a', B.explanation.verdicts?.valuation.label ?? 'n/a'],
                        ['Timing', A.explanation.verdicts?.timing.label ?? A.technical_score.label, B.explanation.verdicts?.timing.label ?? B.technical_score.label],
                        ['Fair value (base)', money(A.fair_value.base), money(B.fair_value.base)],
                        ['Methods', A.fair_value.methods_used.join(', ') || 'None', B.fair_value.methods_used.join(', ') || 'None'],
                      ] as [string, ReactNode, ReactNode][]).map(([k, x, y]) => (
                        <tr key={k}><th scope="row">{k}</th><td>{x}</td><td>{y}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}
        </main>
        <footer className="site"><p>{DISCLAIMER}</p></footer>
      </div>
    </>
  )
}
