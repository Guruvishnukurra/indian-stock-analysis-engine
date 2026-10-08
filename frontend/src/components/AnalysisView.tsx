import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Brain,
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
  Warning,
} from '@phosphor-icons/react'
import { useRef, useState, type ReactNode } from 'react'
import type { Analysis, HistoryRow, MethodResult } from '../lib/api'
import { assessmentTone, crore, dateLabel, isNum, metricValue, money, num, pct, pp, title } from '../lib/format'
import { FairValueChart } from './FairValueChart'
import { PriceChart } from './PriceChart'
import { Sensitivity } from './Sensitivity'
import { StanceBadge } from './Status'

const METHOD_KEYS: [string, string][] = [
  ['dcf', 'DCF'],
  ['growth_dcf', 'Growth-stage DCF'],
  ['peer_pe', 'Peer P/E'],
  ['peer_pb', 'Peer P/B'],
  ['peer_evs', 'Peer EV/Sales'],
  ['historical_pe', 'Historical P/E'],
]

type Tone = 'up' | 'down' | 'warn' | 'neutral'

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

/* ---------------- hero ---------------- */

function Hero({ a }: { a: Analysis }) {
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

      <div className="kpis" role="group" aria-label="Key figures">
        <div className="kpi">
          <span className="label"><Target size={14} />Overall</span>
          <StanceBadge stance={a.explanation.stance} />
          <span className="detail">An analytical view, not advice</span>
        </div>
        <div className="kpi">
          <span className="label"><Scales size={14} />Fair value (base)</span>
          <span className="value">{fv.available ? money(fv.base) : 'n/a'}</span>
          <span className="detail">{fv.available ? `Range ${money(fv.low)} to ${money(fv.high)}` : fv.reason ?? 'Unavailable'}</span>
        </div>
        <div className="kpi">
          <span className="label"><ChartLine size={14} />Upside to base</span>
          <span className={`value delta ${isNum(upside) && upside >= 0 ? 'up' : 'down'}`}>
            {isNum(upside) && (upside >= 0 ? <ArrowUpRight size={20} weight="bold" /> : <ArrowDownRight size={20} weight="bold" />)}
            {pct(upside, true, 0)}
          </span>
          <span className="detail">{a.explanation.verdicts?.valuation.label ?? 'Valuation n/a'}</span>
        </div>
        <div className="kpi">
          <span className="label"><Gauge size={14} />Confidence</span>
          <span className="value">{c.score}<span className="muted small">/100</span></span>
          <div className={`meter ${c.score >= 75 ? 'good' : c.score >= 55 ? '' : 'warn'}`} aria-hidden="true">
            <span style={{ width: `${c.score}%` }} />
          </div>
          <span className="detail">{c.label}</span>
        </div>
        <div className="kpi">
          <span className="label"><ShieldWarning size={14} />Quality</span>
          <span className="value">{q.score != null ? Math.round(q.score) : 'n/a'}<span className="muted small">/100</span></span>
          <span className="detail">{q.label}. Timing: {a.explanation.verdicts?.timing.label?.toLowerCase() ?? 'n/a'}</span>
        </div>
      </div>
    </header>
  )
}

/* ---------------- tabs ---------------- */

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'valuation', label: 'Valuation' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'market', label: 'Market' },
  { id: 'news', label: 'News and risks' },
] as const

type TabId = (typeof TABS)[number]['id']

function Tabs({ active, onChange, counts }: { active: TabId; onChange: (t: TabId) => void; counts: Partial<Record<TabId, number>> }) {
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
    <nav className="tabs" aria-label="Report sections">
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

function Overview({ a }: { a: Analysis }) {
  const fv = a.fair_value
  const growth = a.method_results.growth_dcf
  const simulation = growth?.available ? growth.simulation : undefined
  const gc = a.growth_confidence
  const triggers = a.explanation.verdicts?.triggers ?? []
  const timingNotes = a.explanation.verdicts?.timing.notes ?? []

  return (
    <div className="stack">
      {a.conclusion && (
        <section className="bottom-line" aria-label="Bottom line">
          <div className="eyebrow"><Lightning size={14} weight="fill" />Bottom line</div>
          <p>{a.conclusion}</p>
        </section>
      )}

      <Card title="Fair value" icon={<Scales size={18} />}
        action={fv.available ? <span className="muted small">Methods: {fv.methods_used.join(', ')}</span> : undefined}>
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

      <div className="grid cols-2">
        <Card title="Why bullish" icon={<ThumbsUp size={18} />}>
          <List items={a.explanation.why_bullish} tone="up" icon={<ArrowUpRight size={13} weight="bold" />} />
        </Card>
        <Card title="Why not bullish" icon={<ThumbsDown size={18} />}>
          <List items={a.explanation.why_not_bullish} tone="down" icon={<ArrowDownRight size={13} weight="bold" />} />
        </Card>
      </div>

      <div className="grid cols-2">
        <Card title="Key risks" icon={<ShieldWarning size={18} />}>
          <List items={a.explanation.risks.slice(0, 6)} tone="warn" icon={<Warning size={13} weight="bold" />} />
        </Card>
        <Card title="What would change the verdict" icon={<ArrowRight size={18} />}>
          <List items={triggers} tone="neutral" icon={<ArrowRight size={13} />} empty="No price triggers for this verdict" />
          {timingNotes.map((n) => <p key={n} className="note" style={{ marginTop: 12 }}>{n}</p>)}
        </Card>
      </div>
    </div>
  )
}

/* ---------------- valuation ---------------- */

function MethodsTable({ a }: { a: Analysis }) {
  const weights = a.fair_value.weights_used ?? {}
  const context = a.fair_value.context_methods ?? {}
  return (
    <Card title="Valuation methods" icon={<Scales size={18} />}>
      <div className="table-wrap">
        <table className="stack">
          <thead>
            <tr><th>Method</th><th className="num">Value</th><th className="num">Range</th><th>Weight</th><th>Basis</th></tr>
          </thead>
          <tbody>
            {METHOD_KEYS.map(([key, label]) => {
              const m: MethodResult | undefined = a.method_results[key]
              if (!m) return null
              const weight = weights[key]
              return (
                <tr key={key} className={m.available ? '' : 'excluded'}>
                  <td>{label}{label in context ? ' (context)' : ''}</td>
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

function ValuationTab({ a }: { a: Analysis }) {
  const e = a.expectations
  const growth = a.method_results.growth_dcf
  const dcf = a.method_results.dcf
  const sc = a.scenarios

  return (
    <div className="stack">
      <MethodsTable a={a} />
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
          {sc?.available && sc.cases ? (
            <>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>{sc.horizon_years}-year case</th><th className="num">Growth</th><th className="num">Exit P/E</th><th className="num">Value</th><th className="num">vs price</th></tr></thead>
                  <tbody>
                    {Object.entries(sc.cases).map(([name, c]) => (
                      <tr key={name}>
                        <td>{title(name)}</td>
                        <td className="num">{pct(c.growth * 100)}</td>
                        <td className="num">{num(c.exit_pe, 1)}x</td>
                        <td className="num">{money(c.value)}</td>
                        <td className="num"><span className={`delta ${c.upside >= 0 ? 'up' : 'down'}`}>{pct(c.upside, true, 0)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small" style={{ marginTop: 10 }}>{sc.payoff_summary}</p>
            </>
          ) : (
            <p className="sub">{sc?.reason ?? 'Unavailable'}</p>
          )}
        </Card>
      </div>

      {dcf?.available && dcf.sensitivity && (
        <Card title="DCF sensitivity (₹ per share)" icon={<Database size={18} />}
          action={dcf.terminal_share != null ? <span className="muted small">{Math.round(dcf.terminal_share * 100)}% of value from beyond year 10</span> : undefined}>
          <Sensitivity grid={dcf.sensitivity} price={a.current_price} />
        </Card>
      )}
    </div>
  )
}

/* ---------------- fundamentals ---------------- */

function FundamentalsTab({ a }: { a: Analysis }) {
  const f = a.fundamental_score
  return (
    <div className="stack">
      <p className="sub">Scored against Indian {title(a.company_profile.company_type).toLowerCase()} peers. Each figure shows the period it comes from.</p>
      <div className="metrics">
        {f.metrics.map((m) => {
          const tone = assessmentTone(m.assessment)
          return (
            <div className="metric" key={m.key}>
              <span className="name">{m.label}</span>
              <span className="val">{metricValue(m.value, m.unit)}</span>
              <div className={`meter ${tone}`} role="meter" aria-label={`${m.label} score`} aria-valuenow={Math.round(m.score)} aria-valuemin={0} aria-valuemax={100}>
                <span style={{ width: `${Math.max(m.score, 3)}%` }} />
              </div>
              <div className="row"><span>{m.assessment}, {Math.round(m.score)}/100</span></div>
              <span className="muted small">{m.source ?? 'Period n/a'}</span>
            </div>
          )
        })}
      </div>
      {f.missing.length > 0 && <p className="note">Unavailable: {f.missing.join(', ')}</p>}
    </div>
  )
}

/* ---------------- market ---------------- */

function MarketTab({ a }: { a: Analysis }) {
  const c = a.market_context
  const timing = a.explanation.verdicts?.timing
  const tone = (v?: number | null) => (isNum(v) ? (v >= 0 ? 'up' : 'down') : '')
  return (
    <div className="stack">
      <p className="sub">Technicals describe what the price is doing over the {timing?.horizon ?? 'next few weeks'}, not whether the stock is cheap.</p>
      <div className="grid cols-3-2">
        <Card title="Price, last 12 months" icon={<ChartLine size={18} />}>
          <PriceChart data={a.price_history} />
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
            <div className="stat"><div className="label">Trend</div><div className="val">{a.technical_score.label}</div></div>
          </div>
          <p className="muted small">Sector benchmark: {a.sector_benchmark?.name ?? 'n/a'}</p>
          {timing?.notes.map((n) => <p key={n} className="note">{n}</p>)}
        </div>
      </div>
    </div>
  )
}

/* ---------------- news & risks ---------------- */

function NewsTab({ a, history }: { a: Analysis; history: HistoryRow[] }) {
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
          <div className="grid cols-2" style={{ marginTop: 16 }}>
            <div className="stack"><h3>Catalysts</h3><List items={e.catalysts} tone="up" icon={<ArrowUpRight size={13} weight="bold" />} empty="No material positive events" /></div>
            <div className="stack"><h3>Event risks</h3><List items={e.risks} tone="down" icon={<ArrowDownRight size={13} weight="bold" />} empty="No material negative events" /></div>
          </div>
        ) : (
          <p className="note" style={{ marginTop: 12 }}>Event tagging unavailable (local AI model not running, or news switched off).</p>
        )}
        {(e?.other_material ?? []).length > 0 && (
          <div className="stack" style={{ marginTop: 16 }}><h3>Other material events</h3><List items={e!.other_material!} tone="neutral" icon="-" /></div>
        )}
        {e?.accuracy_note && <p className="muted small" style={{ marginTop: 14 }}>{e.accuracy_note}</p>}
      </Card>

      <div className="grid cols-2">
        <Card title="All risks" icon={<ShieldWarning size={18} />}>
          <List items={a.explanation.risks} tone="warn" icon={<Warning size={13} weight="bold" />} />
        </Card>
        <Card title="Confidence breakdown" icon={<Gauge size={18} />}>
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
  const [tab, setTab] = useState<TabId>('overview')

  const counts: Partial<Record<TabId, number>> = {
    news: a.explanation.risks.length,
    fundamentals: a.fundamental_score.metrics.length,
  }

  return (
    <article>
      <Hero a={a} />
      <Tabs active={tab} onChange={setTab} counts={counts} />
      <div className="tabpanel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} key={tab}>
        {tab === 'overview' && <Overview a={a} />}
        {tab === 'valuation' && <ValuationTab a={a} />}
        {tab === 'fundamentals' && <FundamentalsTab a={a} />}
        {tab === 'market' && <MarketTab a={a} />}
        {tab === 'news' && <NewsTab a={a} history={history} />}
      </div>
    </article>
  )
}
