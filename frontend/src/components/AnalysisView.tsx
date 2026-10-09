import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Brain,
  CaretRight,
  ChartLine,
  ClockCounterClockwise,
  Database,
  Gauge,
  Lightning,
  Newspaper,
  Scales,
  ShieldWarning,
  Target,
  ThumbsDown,
  ThumbsUp,
  TreeStructure,
  Warning,
} from '@phosphor-icons/react'
import { useRef, useState, type ReactNode } from 'react'
import type { Analysis, HistoryRow, MethodResult } from '../lib/api'
import { assessmentTone, crore, dateLabel, isNum, metricValue, money, num, pct, pp, title } from '../lib/format'
import { Drawer } from './Drawer'
import { FairValueChart } from './FairValueChart'
import { PriceChart } from './PriceChart'
import { Sensitivity } from './Sensitivity'
import { StanceBadge } from './Status'
import { type TabTarget, type Trace, traceHeading } from '../lib/traces'
import { TraceBody } from './Traces'

const METHODS: [string, string][] = [
  ['dcf', 'DCF'],
  ['growth_dcf', 'Growth-stage DCF'],
  ['peer_pe', 'Peer P/E'],
  ['peer_pb', 'Peer P/B'],
  ['peer_evs', 'Peer EV/Sales'],
  ['historical_pe', 'Historical P/E'],
]

type Tone = 'up' | 'down' | 'warn' | 'neutral'
type Open = (t: Trace) => void

function List({ items, tone, icon, empty = 'Nothing notable' }: {
  items: string[]; tone: Tone; icon: ReactNode; empty?: string
}) {
  if (!items.length) return <p className="empty-note">{empty}</p>
  return (
    <ul className="list">
      {items.map((item) => (
        <li key={item}><span className={`ic ${tone}`} aria-hidden="true">{icon}</span><span>{item}</span></li>
      ))}
    </ul>
  )
}

function Card({ title: heading, icon, children, action }: {
  title: string; icon?: ReactNode; children: ReactNode; action?: ReactNode
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h2 className="card-title">{icon}{heading}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function ExplainButton({ onClick, children = 'How was this built?' }: { onClick: () => void; children?: ReactNode }) {
  return (
    <button type="button" className="link-btn" onClick={onClick}>
      <TreeStructure size={15} />{children}
    </button>
  )
}

/* Text segmented control: one list visible at a time instead of a long scroll. */
function Explorer({ label, options }: {
  label: string
  options: { id: string; label: string; count?: number; render: () => ReactNode }[]
}) {
  const [active, setActive] = useState(options[0].id)
  const current = options.find((o) => o.id === active) ?? options[0]
  return (
    <div className="explorer">
      <div className="seg" role="tablist" aria-label={label}>
        {options.map((o) => (
          <button key={o.id} type="button" role="tab" aria-selected={o.id === current.id} onClick={() => setActive(o.id)}>
            {o.label}{o.count != null && <span className="count">{o.count}</span>}
          </button>
        ))}
      </div>
      <div className="explorer-body" role="tabpanel" key={current.id}>{current.render()}</div>
    </div>
  )
}

/* ---------------- hero ---------------- */

function Kpi({ icon, label, onClick, children, detail }: {
  icon: ReactNode; label: string; onClick: () => void; children: ReactNode; detail: ReactNode
}) {
  return (
    <button type="button" className="kpi" onClick={onClick}>
      <span className="label">{icon}{label}</span>
      {children}
      <span className="detail">{detail}</span>
      <span className="kpi-cta">How we got here <ArrowRight size={12} weight="bold" /></span>
    </button>
  )
}

function Hero({ a, open }: { a: Analysis; open: Open }) {
  const fv = a.fair_value
  const upside = fv.upside_base
  const c = a.confidence
  const q = a.fundamental_score

  return (
    <header className="hero">
      <div className="hero-top">
        <div className="hero-id">
          <h1>{a.company_name}</h1>
          <div className="hero-tags">
            <span className="tag mono">{a.ticker}</span>
            {a.industry && <span className="tag">{a.industry}</span>}
            <span className="tag">Analysed as {title(a.company_profile.company_type).toLowerCase()}</span>
          </div>
        </div>
        <div className="hero-price">
          <div className="value">{money(a.current_price)}</div>
          <div className="caption">Last price</div>
        </div>
      </div>

      <div className="kpis" role="group" aria-label="Key figures. Select one to see how it was calculated.">
        <Kpi icon={<Target size={14} />} label="Overall" onClick={() => open({ type: 'stance' })} detail="Analytical view, not advice">
          <StanceBadge stance={a.explanation.stance} />
        </Kpi>
        <Kpi icon={<Scales size={14} />} label="Fair value (base)" onClick={() => open({ type: 'fairvalue' })}
          detail={fv.available ? `Range ${money(fv.low)} to ${money(fv.high)}` : fv.reason ?? 'Unavailable'}>
          <span className="value">{fv.available ? money(fv.base) : 'n/a'}</span>
        </Kpi>
        <Kpi icon={<ChartLine size={14} />} label="Upside to base" onClick={() => open({ type: 'upside' })}
          detail={a.explanation.verdicts?.valuation.label ?? 'Valuation n/a'}>
          <span className={`value delta ${isNum(upside) && upside >= 0 ? 'up' : 'down'}`}>
            {isNum(upside) && (upside >= 0 ? <ArrowUpRight size={20} weight="bold" /> : <ArrowDownRight size={20} weight="bold" />)}
            {pct(upside, true, 0)}
          </span>
        </Kpi>
        <Kpi icon={<Gauge size={14} />} label="Confidence" onClick={() => open({ type: 'confidence' })} detail={c.label}>
          <span className="value">{c.score}<span className="muted small">/100</span></span>
          <span className={`meter ${c.score >= 75 ? 'good' : c.score >= 55 ? '' : 'warn'}`} aria-hidden="true">
            <span style={{ width: `${c.score}%` }} />
          </span>
        </Kpi>
        <Kpi icon={<ShieldWarning size={14} />} label="Quality" onClick={() => open({ type: 'quality' })} detail={q.label}>
          <span className="value">{isNum(q.score) ? Math.round(q.score) : 'n/a'}<span className="muted small">/100</span></span>
        </Kpi>
      </div>
    </header>
  )
}

/* ---------------- tabs ---------------- */

const TABS: { id: TabTarget; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'valuation', label: 'Valuation' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'market', label: 'Market' },
  { id: 'news', label: 'News and risks' },
]

function Tabs({ active, onChange, counts }: { active: TabTarget; onChange: (t: TabTarget) => void; counts: Partial<Record<TabTarget, number>> }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([])

  const onKey = (event: React.KeyboardEvent, index: number) => {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    event.preventDefault()
    const next = (index + delta + TABS.length) % TABS.length
    onChange(TABS[next].id)
    refs.current[next]?.focus()
  }

  return (
    <nav className="tabs" id="report-tabs" aria-label="Report sections">
      <div className="tablist" role="tablist">
        {TABS.map((t, i) => (
          <button key={t.id} ref={(el) => { refs.current[i] = el }} role="tab" id={`tab-${t.id}`}
            aria-selected={active === t.id} aria-controls={`panel-${t.id}`} tabIndex={active === t.id ? 0 : -1}
            className="tab" onClick={() => onChange(t.id)} onKeyDown={(e) => onKey(e, i)}>
            {t.label}
            {counts[t.id] ? <span className="count">{counts[t.id]}</span> : null}
          </button>
        ))}
      </div>
    </nav>
  )
}

/* ---------------- overview ---------------- */

function VerdictPath({ a, open }: { a: Analysis; open: Open }) {
  const v = a.explanation.verdicts
  const timing = v?.timing.label ?? a.technical_score.label
  const valuation = v?.valuation.label ?? 'n/a'
  const nodes: { label: string; value: string; tone: string; trace: Trace }[] = [
    { label: 'Quality', value: v?.quality ?? a.fundamental_score.label, tone: assessmentTone(v?.quality ?? a.fundamental_score.label), trace: { type: 'quality' } },
    { label: 'Valuation', value: valuation, tone: valuation === 'Undervalued' ? 'good' : valuation === 'Overvalued' ? 'bad' : 'warn', trace: { type: 'upside' } },
    { label: 'Timing', value: timing, tone: /strong|positive/i.test(timing) ? 'good' : /weak|negative/i.test(timing) ? 'bad' : 'warn', trace: { type: 'timing' } },
    { label: 'Confidence', value: `${a.confidence.score}/100`, tone: a.confidence.score >= 75 ? 'good' : a.confidence.score >= 50 ? 'warn' : 'bad', trace: { type: 'confidence' } },
  ]
  return (
    <section className="card" aria-labelledby="path-title">
      <div className="card-head">
        <h2 className="card-title" id="path-title"><TreeStructure size={18} />How the verdict was reached</h2>
        <span className="muted small">Select any step</span>
      </div>
      <ol className="vpath">
        {nodes.map((n) => (
          <li key={n.label}>
            <button type="button" className={`vnode ${n.tone}`} onClick={() => open(n.trace)}>
              <span className="vlabel">{n.label}</span>
              <span className="vvalue">{n.value}</span>
            </button>
            <CaretRight size={16} className="varrow" aria-hidden="true" />
          </li>
        ))}
        <li>
          <button type="button" className="vnode result" onClick={() => open({ type: 'stance' })}>
            <span className="vlabel">Stance</span>
            <StanceBadge stance={a.explanation.stance} />
          </button>
        </li>
      </ol>
    </section>
  )
}

function Overview({ a, open }: { a: Analysis; open: Open }) {
  const fv = a.fair_value
  const growth = a.method_results.growth_dcf
  const simulation = growth?.available ? growth.simulation : undefined
  const gc = a.growth_confidence
  const triggers = a.explanation.verdicts?.triggers ?? []
  const timingNotes = a.explanation.verdicts?.timing.notes ?? []
  const ex = a.explanation

  return (
    <div className="stack">
      {a.conclusion && (
        <section className="bottom-line" aria-label="Bottom line">
          <div className="eyebrow"><Lightning size={14} weight="fill" />Bottom line</div>
          <p>{a.conclusion}</p>
        </section>
      )}

      <VerdictPath a={a} open={open} />

      <Card title="Fair value" icon={<Scales size={18} />}
        action={fv.available ? <ExplainButton onClick={() => open({ type: 'fairvalue' })} /> : undefined}>
        {fv.available ? (
          <FairValueChart fairValue={fv} price={a.current_price} consensus={a.inputs.consensus_target}
            growthRange={simulation ? { p10: simulation.p10, p90: simulation.p90 } : null} />
        ) : (
          <p className="sub">{fv.reason ?? 'No fair value could be produced.'}</p>
        )}
        {gc && fv.methods_used.includes('Growth-stage DCF') && (
          <div className="callout" role="note" style={{ marginTop: 16 }}>
            <span className="ic" aria-hidden="true"><Warning size={16} weight="bold" /></span>
            <div>
              <strong>Growth-stage valuation confidence: {gc.level.toLowerCase()}</strong>
              <p className="small secondary">Not a conventional intrinsic value: it depends heavily on assumed future profitability.</p>
              <ul className="list small" style={{ marginTop: 10 }}>
                {gc.reasons.map((r) => <li key={r}><span className="ic neutral" aria-hidden="true">-</span><span>{r}</span></li>)}
              </ul>
            </div>
          </div>
        )}
      </Card>

      <Card title="The case, both ways" icon={<Scales size={18} />}>
        <Explorer label="Case" options={[
          { id: 'bull', label: 'Bull case', count: ex.why_bullish.length, render: () => <List items={ex.why_bullish} tone="up" icon={<ThumbsUp size={12} weight="bold" />} /> },
          { id: 'bear', label: 'Bear case', count: ex.why_not_bullish.length, render: () => <List items={ex.why_not_bullish} tone="down" icon={<ThumbsDown size={12} weight="bold" />} /> },
          { id: 'risks', label: 'Key risks', count: Math.min(ex.risks.length, 6), render: () => <List items={ex.risks.slice(0, 6)} tone="warn" icon={<Warning size={13} weight="bold" />} /> },
          { id: 'change', label: 'What would change it', count: triggers.length, render: () => (
            <>
              <List items={triggers} tone="neutral" icon={<ArrowRight size={13} />} empty="No price triggers for this verdict" />
              {timingNotes.map((n) => <p key={n} className="note" style={{ marginTop: 12 }}>{n}</p>)}
            </>
          ) },
        ]} />
      </Card>
    </div>
  )
}

/* ---------------- valuation ---------------- */

function MethodsTable({ a, open }: { a: Analysis; open: Open }) {
  const weights = a.fair_value.weights_used ?? {}
  const context = a.fair_value.context_methods ?? {}
  return (
    <Card title="Valuation methods" icon={<Scales size={18} />} action={<span className="muted small">Select a method for its inputs</span>}>
      <div className="table-wrap">
        <table className="stack clickable">
          <thead>
            <tr><th>Method</th><th className="num">Value</th><th className="num">Range</th><th>Weight</th><th>Basis</th></tr>
          </thead>
          <tbody>
            {METHODS.map(([key, label]) => {
              const m: MethodResult | undefined = a.method_results[key]
              if (!m) return null
              const weight = weights[key]
              return (
                <tr key={key} className={m.available ? '' : 'excluded'} onClick={() => open({ type: 'method', key })}>
                  <td>
                    <button type="button" className="row-link" onClick={(e) => { e.stopPropagation(); open({ type: 'method', key }) }}>
                      {label}{label in context ? ' (context)' : ''}<CaretRight size={13} aria-hidden="true" />
                    </button>
                  </td>
                  <td className="num" data-label="Value">{m.available ? money(m.base) : 'n/a'}</td>
                  <td className="num" data-label="Range">{m.available ? `${money(m.low)} to ${money(m.high)}` : 'n/a'}</td>
                  <td data-label="Weight" style={{ whiteSpace: 'nowrap' }}>
                    {weight ? (<><span className="weight-bar" aria-hidden="true"><span style={{ width: `${weight * 100}%` }} /></span><span className="mono">{Math.round(weight * 100)}%</span></>) : <span className="muted">n/a</span>}
                  </td>
                  <td className="small">{m.available ? m.range_basis : m.reason}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {(a.inputs.risk_premium_reasons ?? []).length > 0 && (
        <p className="note" style={{ marginTop: 12 }}>Discount-rate risk premium: {a.inputs.risk_premium_reasons!.join('; ')}</p>
      )}
    </Card>
  )
}

function ScenarioExplorer({ a }: { a: Analysis }) {
  const sc = a.scenarios
  const [pick, setPick] = useState('base')
  if (!sc?.available || !sc.cases) return <p className="sub">{sc?.reason ?? 'Unavailable'}</p>
  const cases = sc.cases
  const names = ['bear', 'base', 'bull'].filter((n) => cases[n])
  const c = cases[pick] ?? cases[names[0]]
  const vals = [...names.map((n) => cases[n].value), a.current_price]
  const lo = Math.min(...vals) * 0.9
  const hi = Math.max(...vals) * 1.05
  const at = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`

  return (
    <div className="stack">
      <div className="seg" role="radiogroup" aria-label="Scenario">
        {names.map((n) => (
          <button key={n} type="button" role="radio" aria-checked={pick === n} onClick={() => setPick(n)}>{title(n)} case</button>
        ))}
      </div>
      <div className="scenario-read" aria-live="polite">
        <div>
          <div className="big-num">{money(c.value)}</div>
          <span className={`delta ${c.upside >= 0 ? 'up' : 'down'}`}>{pct(c.upside, true, 0)} vs today, in {sc.horizon_years} years</span>
        </div>
        <dl className="kv compact">
          <div><dt>Earnings growth</dt><dd>{pct(c.growth * 100)} a year</dd></div>
          <div><dt>Exit P/E</dt><dd>{num(c.exit_pe, 1)}x</dd></div>
        </dl>
      </div>
      <div className="scale">
        <div className="scale-track" />
        <div className="scale-price" style={{ left: at(a.current_price) }}><span>Price {money(a.current_price)}</span></div>
        {names.map((n) => (
          <button key={n} type="button" tabIndex={-1} aria-hidden="true" className={`scale-dot ${n}${pick === n ? ' on' : ''}`}
            style={{ left: at(cases[n].value) }} onClick={() => setPick(n)} title={`${title(n)}: ${money(cases[n].value)}`} />
        ))}
      </div>
      <p className="muted small">{sc.payoff_summary}</p>
    </div>
  )
}

function ValuationTab({ a, open }: { a: Analysis; open: Open }) {
  const e = a.expectations
  const growth = a.method_results.growth_dcf
  const dcf = a.method_results.dcf

  return (
    <div className="stack">
      <MethodsTable a={a} open={open} />
      <div className="grid cols-2">
        <Card title="What the price assumes" icon={<Target size={18} />}>
          {e?.available ? (
            <div className="stack">
              <span className={`stance ${e.assessment === 'Undemanding' || e.assessment?.startsWith('Consistent') ? 'good' : e.assessment === 'Demanding' ? 'warn' : 'bad'}`}>
                {e.assessment}
              </span>
              <p className="secondary">{e.summary}</p>
              <p className="muted small">{e.method}</p>
            </div>
          ) : (
            <p className="sub">{e?.reason ?? 'Unavailable'}</p>
          )}
          {growth?.simulation && (
            <div className="stack" style={{ marginTop: 18 }}>
              <h3>Simulated futures ({growth.simulation.runs.toLocaleString('en-IN')})</h3>
              <div className="stats">
                <div className="stat"><div className="label">10th percentile</div><div className="val">{money(growth.simulation.p10)}</div></div>
                <div className="stat"><div className="label">Median</div><div className="val">{money(growth.simulation.p50)}</div></div>
                <div className="stat"><div className="label">90th percentile</div><div className="val">{money(growth.simulation.p90)}</div></div>
                <div className="stat"><div className="label">Justify today's price</div><div className="val">{Math.round(growth.simulation.share_justifying_price * 100)}%</div></div>
              </div>
              {growth.funding?.first_positive_fcf_year && (
                <p className="note">
                  Cash-positive from about year {growth.funding.first_positive_fcf_year}. Peak cumulative burn {crore(growth.funding.peak_cash_burn)} vs net cash {crore(growth.funding.net_cash)}.
                  {growth.funding.funding_gap > 0 && growth.funding.gap_share_of_market_cap != null && (
                    <> Funding gap about {crore(growth.funding.funding_gap)} (~{Math.round(growth.funding.gap_share_of_market_cap * 100)}% of market cap): likely dilution.</>
                  )}
                </p>
              )}
            </div>
          )}
        </Card>

        <Card title="Scenarios" icon={<ChartLine size={18} />}>
          <ScenarioExplorer a={a} />
        </Card>
      </div>

      {dcf?.available && dcf.sensitivity && (
        <Card title="DCF sensitivity (₹ per share)" icon={<Database size={18} />}
          action={<ExplainButton onClick={() => open({ type: 'method', key: 'dcf' })}>DCF inputs</ExplainButton>}>
          <Sensitivity grid={dcf.sensitivity} price={a.current_price} />
          {dcf.terminal_share != null && <p className="muted small" style={{ marginTop: 8 }}>{Math.round(dcf.terminal_share * 100)}% of the DCF value comes from beyond year 10.</p>}
        </Card>
      )}
    </div>
  )
}

/* ---------------- fundamentals ---------------- */

function FundamentalsTab({ a, open }: { a: Analysis; open: Open }) {
  const f = a.fundamental_score
  return (
    <div className="stack">
      <div className="row-between">
        <p className="sub">Scored against Indian {title(a.company_profile.company_type).toLowerCase()} peers. Select a metric for what it means.</p>
        <ExplainButton onClick={() => open({ type: 'quality' })}>How the score combines</ExplainButton>
      </div>
      <div className="metrics">
        {f.metrics.map((m) => {
          const tone = assessmentTone(m.assessment)
          return (
            <button type="button" className="metric" key={m.key} onClick={() => open({ type: 'metric', key: m.key })}>
              <span className="name">{m.label}</span>
              <span className="val">{metricValue(m.value, m.unit)}</span>
              <span className={`meter ${tone}`} aria-hidden="true"><span style={{ width: `${Math.max(m.score, 3)}%` }} /></span>
              <span className="row"><span>{m.assessment}, {Math.round(m.score)}/100</span><CaretRight size={13} aria-hidden="true" /></span>
              <span className="muted small">{m.source ?? 'Period n/a'}</span>
            </button>
          )
        })}
      </div>
      {f.missing.length > 0 && <p className="note">Unavailable: {f.missing.join(', ')}</p>}
    </div>
  )
}

/* ---------------- market ---------------- */

const RANGES = [['3M', 63], ['6M', 126], ['1Y', 260]] as const

function MarketTab({ a, open }: { a: Analysis; open: Open }) {
  const c = a.market_context
  const timing = a.explanation.verdicts?.timing
  const [range, setRange] = useState<number>(260)
  const tone = (v?: number | null) => (isNum(v) ? (v >= 0 ? 'up' : 'down') : '')
  const data = a.price_history.slice(-range)
  return (
    <div className="stack">
      <p className="sub">Technicals describe what the price is doing over the {timing?.horizon ?? 'next few weeks'}, not whether the stock is cheap.</p>
      <div className="grid cols-3-2">
        <Card title="Price" icon={<ChartLine size={18} />}
          action={
            <div className="seg sm" role="radiogroup" aria-label="Chart range">
              {RANGES.map(([l, d]) => <button key={l} type="button" role="radio" aria-checked={range === d} onClick={() => setRange(d)}>{l}</button>)}
            </div>
          }>
          <PriceChart data={data} />
        </Card>
        <div className="stack">
          <div className="stats">
            <div className="stat"><div className="label">Stock, 30 days</div><div className={`val delta ${tone(c.stock_return)}`}>{pct(c.stock_return)}</div></div>
            <div className="stat"><div className="label">NIFTY, 30 days</div><div className={`val delta ${tone(c.market_return)}`}>{pct(c.market_return)}</div></div>
            <div className="stat"><div className="label">Relative to NIFTY</div><div className={`val delta ${tone(c.relative_to_market)}`}>{pp(c.relative_to_market)}</div></div>
            <div className="stat"><div className="label">Sector, 30 days</div><div className={`val delta ${tone(c.sector_return)}`}>{pct(c.sector_return)}</div></div>
            <div className="stat"><div className="label">Relative to sector</div><div className={`val delta ${tone(c.relative_to_sector)}`}>{pp(c.relative_to_sector)}</div></div>
            <div className="stat"><div className="label">RSI (14)</div><div className="val">{num(a.latest_technical?.RSI_14, 1)}</div></div>
            <div className="stat"><div className="label">Beta vs NIFTY</div><div className="val">{num(a.beta)}</div></div>
            <button type="button" className="stat stat-btn" onClick={() => open({ type: 'timing' })}>
              <span className="label">Trend <CaretRight size={12} aria-hidden="true" /></span><span className="val">{a.technical_score.label}</span>
            </button>
          </div>
          <p className="muted small">Sector benchmark: {a.sector_benchmark?.name ?? 'n/a'}</p>
          {timing?.notes.map((n) => <p key={n} className="note">{n}</p>)}
        </div>
      </div>
    </div>
  )
}

/* ---------------- news & risks ---------------- */

function NewsTab({ a, history, open }: { a: Analysis; history: HistoryRow[]; open: Open }) {
  const n = a.news
  const e = n.events
  const ml = a.ml_trend
  return (
    <div className="stack">
      <Card title="News events" icon={<Newspaper size={18} />}
        action={<span className="muted small">{n.raw_article_count ?? 0} articles, {n.duplicates_removed ?? 0} duplicates removed</span>}>
        <p className="sub">
          Sentiment {n.label?.toLowerCase() ?? 'n/a'}{isNum(n.news_score) ? ` (${Math.round(n.news_score)}/100)` : ''}
          {n.sentiment_basis ? `, scored on ${n.sentiment_basis}` : ''}.
          {e?.material_share != null ? ` ${Math.round(e.material_share * 100)}% of headlines were material events.` : ''}
        </p>
        {e ? (
          <div style={{ marginTop: 16 }}>
            <Explorer label="News events" options={[
              { id: 'cat', label: 'Catalysts', count: e.catalysts.length, render: () => <List items={e.catalysts} tone="up" icon={<ArrowUpRight size={13} weight="bold" />} empty="No material positive events" /> },
              { id: 'risk', label: 'Event risks', count: e.risks.length, render: () => <List items={e.risks} tone="down" icon={<ArrowDownRight size={13} weight="bold" />} empty="No material negative events" /> },
              { id: 'other', label: 'Other material', count: (e.other_material ?? []).length, render: () => <List items={e.other_material ?? []} tone="neutral" icon="-" empty="Nothing else material" /> },
            ]} />
          </div>
        ) : (
          <p className="note" style={{ marginTop: 12 }}>Event tagging unavailable (local AI model not running, or news switched off).</p>
        )}
        {e?.accuracy_note && <p className="muted small" style={{ marginTop: 14 }}>{e.accuracy_note}</p>}
      </Card>

      <div className="grid cols-2">
        <Card title="All risks" icon={<ShieldWarning size={18} />}>
          <List items={a.explanation.risks} tone="warn" icon={<Warning size={13} weight="bold" />} />
        </Card>
        <Card title="Confidence breakdown" icon={<Gauge size={18} />} action={<ExplainButton onClick={() => open({ type: 'confidence' })}>Score by check</ExplainButton>}>
          <List items={a.confidence.reasons} tone="up" icon={<ThumbsUp size={12} weight="bold" />} empty="No strengths recorded" />
          <div style={{ marginTop: 12 }}><List items={a.confidence.concerns} tone="down" icon={<Warning size={12} weight="bold" />} empty="No concerns recorded" /></div>
        </Card>
      </div>

      {a.thesis?.available && (
        <Card title="AI-written thesis" icon={<Brain size={18} />}>
          <p style={{ whiteSpace: 'pre-line', maxWidth: '80ch' }}>{a.thesis.text}</p>
          <p className="muted small" style={{ marginTop: 10 }}>{a.thesis.note}</p>
        </Card>
      )}

      <div className="grid cols-2">
        <Card title="ML trend outlook" icon={<Brain size={18} />}>
          {ml.available ? <p>Model available.</p> : (
            <div className="stack">
              <span className="stance neutral">Unavailable</span>
              <p className="secondary small">The trend model is hidden because it has not beaten simple baselines out of sample.</p>
              {ml.validation && <p className="note">Edge over best baseline {pp(ml.validation.edge * 100)}, required {pp(ml.validation.required_edge * 100)}.</p>}
            </div>
          )}
        </Card>
        <Card title="Data limitations" icon={<Database size={18} />}>
          <List items={a.explanation.data_limitations} tone="neutral" icon="-" />
        </Card>
      </div>

      {history.length > 1 && (
        <Card title="Past analyses" icon={<ClockCounterClockwise size={18} />}>
          <div className="table-wrap">
            <table className="stack">
              <thead><tr><th>Date</th><th>Stance</th><th className="num">Price</th><th className="num">Fair value</th><th className="num">Confidence</th></tr></thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.job_id}>
                    <td>{dateLabel(r.created_at)}</td>
                    <td data-label="Stance">{r.stance ? <StanceBadge stance={r.stance} /> : 'n/a'}</td>
                    <td className="num" data-label="Price">{money(r.price)}</td>
                    <td className="num" data-label="Fair value">{r.fair_value_base ? `${money(r.fair_value_low)} to ${money(r.fair_value_high)}` : 'n/a'}</td>
                    <td className="num" data-label="Confidence">{r.confidence ?? 'n/a'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ---------------- page ---------------- */

export function AnalysisView({ analysis: a, history }: { analysis: Analysis; history: HistoryRow[] }) {
  const [tab, setTab] = useState<TabTarget>('overview')
  const [trace, setTrace] = useState<Trace | null>(null)

  const counts: Partial<Record<TabTarget, number>> = {
    news: a.explanation.risks.length,
    fundamentals: a.fundamental_score.metrics.length,
  }

  const jump = (t: TabTarget) => {
    setTrace(null)
    setTab(t)
    requestAnimationFrame(() => document.getElementById('report-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const heading = trace ? traceHeading(trace, a) : null

  return (
    <article>
      <Hero a={a} open={setTrace} />
      <Tabs active={tab} onChange={setTab} counts={counts} />
      <div className="tabpanel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} key={tab}>
        {tab === 'overview' && <Overview a={a} open={setTrace} />}
        {tab === 'valuation' && <ValuationTab a={a} open={setTrace} />}
        {tab === 'fundamentals' && <FundamentalsTab a={a} open={setTrace} />}
        {tab === 'market' && <MarketTab a={a} open={setTrace} />}
        {tab === 'news' && <NewsTab a={a} history={history} open={setTrace} />}
      </div>
      <Drawer open={trace != null} title={heading?.title ?? ''} eyebrow={heading ? `${heading.eyebrow}: how we got here` : undefined}
        onClose={() => setTrace(null)}>
        {trace && <TraceBody trace={trace} a={a} onJump={jump} />}
      </Drawer>
    </article>
  )
}
