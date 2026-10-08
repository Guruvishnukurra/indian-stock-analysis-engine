import type { Analysis, HistoryRow, MethodResult } from '../lib/api'
import { crore, dateLabel, metricValue, money, num, pct, pp, title } from '../lib/format'
import { FairValueChart } from './FairValueChart'
import { PriceChart } from './PriceChart'
import { Sensitivity } from './Sensitivity'
import { AssessmentPill, StanceBadge } from './Status'

const METHOD_KEYS: [string, string][] = [
  ['dcf', 'DCF'],
  ['growth_dcf', 'Growth-stage DCF'],
  ['peer_pe', 'Peer P/E'],
  ['peer_pb', 'Peer P/B'],
  ['peer_evs', 'Peer EV/Sales'],
  ['historical_pe', 'Historical P/E'],
]

function List({ items, mark, tone }: { items: string[]; mark: string; tone: 'good' | 'bad' | 'neutral' }) {
  if (!items.length) return <p className="muted small">None</p>
  return (
    <ul className="plain">
      {items.map((item) => (
        <li key={item}><span className={`mark ${tone}`} aria-hidden="true">{mark}</span><span>{item}</span></li>
      ))}
    </ul>
  )
}

function Header({ a }: { a: Analysis }) {
  return (
    <header className="company">
      <div>
        <h1>{a.company_name}</h1>
        <p className="meta">
          <span className="mono">{a.ticker}</span>, {a.industry ?? a.sector ?? 'industry n/a'}.
          Analysed as {title(a.company_profile.company_type).toLowerCase()}.
        </p>
      </div>
      <div className="price">
        {money(a.current_price)}
        <small>last price</small>
      </div>
    </header>
  )
}

function Verdicts({ a }: { a: Analysis }) {
  const v = a.explanation.verdicts
  const confidence = a.confidence
  return (
    <section className="verdicts" aria-label="Verdict summary">
      <div className="verdict">
        <span className="label">Overall</span>
        <span className="tile-value"><StanceBadge stance={a.explanation.stance} /></span>
        <span className="note">An analytical view, not advice</span>
      </div>
      <div className="verdict">
        <span className="label">Quality</span>
        <span className="tile-value">{v?.quality ?? 'n/a'}</span>
        <span className="note">Fundamentals {a.fundamental_score.score != null ? `${Math.round(a.fundamental_score.score)}/100` : 'n/a'}</span>
      </div>
      <div className="verdict">
        <span className="label">Valuation</span>
        <span className="tile-value">{v?.valuation.label ?? 'n/a'}</span>
        <span className="note">
          {v?.valuation.fair_value_to_price != null ? `Fair value ${v.valuation.fair_value_to_price.toFixed(2)}x price` : 'No fair value'}
        </span>
      </div>
      <div className="verdict">
        <span className="label">Timing</span>
        <span className="tile-value">{v?.timing.label ?? 'n/a'}</span>
        <span className="note">Over the {v?.timing.horizon ?? 'next few weeks'}</span>
      </div>
      <div className="verdict">
        <span className="label">Confidence</span>
        <span className="tile-value">{confidence.label} <span className="muted mono small">{confidence.score}/100</span></span>
        <div className="meter" role="meter" aria-label="Confidence" aria-valuenow={confidence.score} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${confidence.score}%` }} />
        </div>
      </div>
    </section>
  )
}

function FairValueSection({ a }: { a: Analysis }) {
  const fv = a.fair_value
  const growth = a.method_results.growth_dcf
  const simulation = growth?.available ? growth.simulation : undefined
  const gc = a.growth_confidence
  const triggers = a.explanation.verdicts?.triggers ?? []

  return (
    <div className="panel section">
      <h2>Fair value</h2>
      {fv.available ? (
        <>
          <p className="sub">
            Range <b className="mono">{money(fv.low)} to {money(fv.high)}</b>, base <b className="mono">{money(fv.base)}</b> ({pct(fv.upside_base)} vs price).
            Methods: {fv.methods_used.join(', ')}.
          </p>
          <FairValueChart
            fairValue={fv}
            price={a.current_price}
            consensus={a.inputs.consensus_target}
            growthRange={simulation ? { p10: simulation.p10, p90: simulation.p90 } : null}
          />
        </>
      ) : (
        <p className="secondary">{fv.reason ?? 'No fair value could be produced.'}</p>
      )}

      {gc && fv.methods_used.includes('Growth-stage DCF') && (
        <div className="callout" role="note">
          <strong>Growth-stage valuation confidence: {gc.level}</strong>
          <p className="small">
            This is not a conventional intrinsic-value estimate. It depends heavily on assumed future profitability.
          </p>
          <List items={gc.reasons} mark="-" tone="neutral" />
        </div>
      )}

      {triggers.length > 0 && (
        <div className="section">
          <h3>What would change the verdict</h3>
          <List items={triggers} mark="→" tone="neutral" />
        </div>
      )}

      {a.inputs.consensus_target ? (
        <p className="muted small section">
          Analyst consensus (reference only, never used in the fair value): {money(a.inputs.consensus_target)}
          {a.inputs.analyst_count ? ` from ${a.inputs.analyst_count} analysts` : ''}.
        </p>
      ) : null}
    </div>
  )
}

function MethodsTable({ a }: { a: Analysis }) {
  const weights = a.fair_value.weights_used ?? {}
  const context = a.fair_value.context_methods ?? {}
  return (
    <div className="panel">
      <h2>Valuation methods</h2>
      <div className="table-wrap">
        <table className="stack">
          <thead>
            <tr><th>Method</th><th className="num">Value</th><th className="num">Range</th><th className="num">Weight</th><th>Basis / reason</th></tr>
          </thead>
          <tbody>
            {METHOD_KEYS.map(([key, label]) => {
              const m: MethodResult | undefined = a.method_results[key]
              if (!m) return null
              const weight = weights[key]
              const isContext = label in context
              return (
                <tr key={key} className={m.available ? '' : 'excluded'}>
                  <td>{label}{isContext ? ' (context only)' : ''}</td>
                  <td className="num" data-label="Value">{m.available ? money(m.base) : 'n/a'}</td>
                  <td className="num" data-label="Range">{m.available ? `${money(m.low)} to ${money(m.high)}` : 'n/a'}</td>
                  <td className="num" data-label="Weight">{weight ? `${Math.round(weight * 100)}%` : 'n/a'}</td>
                  <td className="small">{m.available ? m.range_basis : m.reason}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {(a.inputs.risk_premium_reasons ?? []).length > 0 && (
        <p className="muted small section">Discount-rate risk premium: {a.inputs.risk_premium_reasons!.join('; ')}</p>
      )}
    </div>
  )
}

function Expectations({ a }: { a: Analysis }) {
  const e = a.expectations
  const growth = a.method_results.growth_dcf
  const dcf = a.method_results.dcf
  const sc = a.scenarios

  return (
    <div className="panel">
      <h2>What the price assumes</h2>
      {e?.available ? (
        <>
          <p><AssessmentPill label={e.assessment === 'Undemanding' || e.assessment?.startsWith('Consistent') ? 'Strong' : e.assessment === 'Demanding' ? 'Moderate' : 'Weak'} /> <b>{e.assessment}</b></p>
          <p className="secondary section">{e.summary}</p>
          <p className="muted small">{e.method}</p>
        </>
      ) : (
        <p className="secondary">{e?.reason ?? 'Unavailable'}</p>
      )}

      {growth?.simulation && (
        <div className="section">
          <h3>Simulated futures</h3>
          <p className="secondary small">
            {growth.simulation.runs.toLocaleString('en-IN')} futures (growth, peer-based mature margin, discount rate, capital needs):
            the 10th, 50th and 90th percentile values are {money(growth.simulation.p10)}, {money(growth.simulation.p50)} and {money(growth.simulation.p90)}.{' '}
            <b>{Math.round(growth.simulation.share_justifying_price * 100)}% justify today's price.</b>
          </p>
          {growth.funding?.first_positive_fcf_year && (
            <p className="secondary small">
              Cash-positive from about year {growth.funding.first_positive_fcf_year}; peak cumulative burn {crore(growth.funding.peak_cash_burn)} vs net cash {crore(growth.funding.net_cash)}.
              {growth.funding.funding_gap > 0 && growth.funding.gap_share_of_market_cap != null && (
                <> Funding gap about {crore(growth.funding.funding_gap)} (~{Math.round(growth.funding.gap_share_of_market_cap * 100)}% of market cap): likely dilution.</>
              )}
            </p>
          )}
        </div>
      )}

      {sc?.available && sc.cases && (
        <div className="section">
          <h3>Scenarios ({sc.horizon_years}-year, value today)</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Case</th><th className="num">Growth</th><th className="num">Exit P/E</th><th className="num">Value</th><th className="num">vs price</th></tr></thead>
              <tbody>
                {Object.entries(sc.cases).map(([name, c]) => (
                  <tr key={name}>
                    <td>{title(name)}</td>
                    <td className="num">{pct(c.growth * 100)}</td>
                    <td className="num">{num(c.exit_pe, 1)}x</td>
                    <td className="num">{money(c.value)}</td>
                    <td className="num">{pct(c.upside)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted small">{sc.payoff_summary}</p>
        </div>
      )}

      {dcf?.available && dcf.sensitivity && (
        <div className="section">
          <h3>DCF sensitivity (₹ per share)</h3>
          <Sensitivity grid={dcf.sensitivity} price={a.current_price} />
          {dcf.terminal_share != null && (
            <p className="muted small">{Math.round(dcf.terminal_share * 100)}% of DCF value comes from beyond year 10.</p>
          )}
        </div>
      )}
    </div>
  )
}

function Fundamentals({ a }: { a: Analysis }) {
  const f = a.fundamental_score
  return (
    <div className="panel">
      <h2>Fundamentals ({title(a.company_profile.company_type)} metrics)</h2>
      <div className="table-wrap">
        <table className="stack">
          <thead><tr><th>Metric</th><th className="num">Value</th><th>Assessment</th><th>Period</th></tr></thead>
          <tbody>
            {f.metrics.map((m) => (
              <tr key={m.key}>
                <td>{m.label}</td>
                <td className="num" data-label="Value">{metricValue(m.value, m.unit)}</td>
                <td data-label="Assessment"><AssessmentPill label={m.assessment} /> <span className="muted small">{Math.round(m.score)}/100</span></td>
                <td className="small secondary" data-label="Period">{m.source ?? 'n/a'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {f.missing.length > 0 && <p className="muted small section">Unavailable: {f.missing.join(', ')}</p>}
    </div>
  )
}

function Market({ a }: { a: Analysis }) {
  const c = a.market_context
  const timing = a.explanation.verdicts?.timing
  return (
    <div className="panel section">
      <h2>Current market condition</h2>
      <p className="sub">Technicals describe what the price is doing, not whether the stock is cheap.</p>
      <div className="grid two section">
        <PriceChart data={a.price_history} />
        <div className="table-wrap">
          <table>
            <tbody>
              <tr><td>Stock 30-day return</td><td className="num">{pct(c.stock_return)}</td></tr>
              <tr><td>NIFTY 30-day return</td><td className="num">{pct(c.market_return)}</td></tr>
              <tr><td>Stock relative to NIFTY</td><td className="num">{pp(c.relative_to_market)}</td></tr>
              <tr><td>Sector 30-day return <span className="muted small">({a.sector_benchmark?.name ?? 'n/a'})</span></td><td className="num">{pct(c.sector_return)}</td></tr>
              <tr><td>Stock relative to sector</td><td className="num">{pp(c.relative_to_sector)}</td></tr>
              <tr><td>RSI (14)</td><td className="num">{num(a.latest_technical?.RSI_14, 1)}</td></tr>
              <tr><td>Beta vs NIFTY</td><td className="num">{num(a.beta)}</td></tr>
              <tr><td>Technical trend</td><td className="num">{a.technical_score.label}</td></tr>
            </tbody>
          </table>
          {timing?.notes.map((n) => <p key={n} className="note-box">{n}</p>)}
        </div>
      </div>
    </div>
  )
}

function News({ a }: { a: Analysis }) {
  const n = a.news
  const e = n.events
  return (
    <div className="panel">
      <h2>News & events</h2>
      <p className="sub">
        Sentiment {n.label ?? 'n/a'}{n.news_score != null ? ` (${Math.round(n.news_score)}/100)` : ''}
        {n.sentiment_basis ? `, scored on ${n.sentiment_basis}` : ''}
      </p>
      <p className="muted small">
        {n.raw_article_count ?? 0} articles fetched, {n.duplicates_removed ?? 0} duplicates removed
        {e?.material_share != null ? `. ${Math.round(e.material_share * 100)}% material events, ${Math.round((e.noise_share ?? 0) * 100)}% price commentary or off-topic` : ''}
      </p>
      {e ? (
        <div className="section grid">
          <div><h3>Catalysts</h3><List items={e.catalysts} mark="+" tone="good" /></div>
          <div><h3>Event risks</h3><List items={e.risks} mark="−" tone="bad" /></div>
          {(e.other_material ?? []).length > 0 && (
            <div><h3>Other material events</h3><List items={e.other_material!} mark="-" tone="neutral" /></div>
          )}
          {e.accuracy_note && <p className="muted small">{e.accuracy_note}</p>}
        </div>
      ) : (
        <p className="muted small section">Event tagging unavailable (local LLM not running or news not requested).</p>
      )}
    </div>
  )
}

function Reasons({ a }: { a: Analysis }) {
  const x = a.explanation
  return (
    <div className="grid two section">
      <div className="panel"><h2>Why bullish</h2><List items={x.why_bullish} mark="+" tone="good" /></div>
      <div className="panel"><h2>Why not bullish</h2><List items={x.why_not_bullish} mark="−" tone="bad" /></div>
      <div className="panel"><h2>Risks</h2><List items={x.risks} mark="!" tone="bad" /></div>
      <div className="panel">
        <h2>Confidence</h2>
        <List items={a.confidence.reasons} mark="✓" tone="good" />
        <div className="section"><List items={a.confidence.concerns} mark="!" tone="bad" /></div>
      </div>
    </div>
  )
}

function Ml({ a }: { a: Analysis }) {
  const ml = a.ml_trend
  return (
    <div className="panel">
      <h2>ML trend outlook</h2>
      {ml.available ? (
        <p>Model available.</p>
      ) : (
        <>
          <p><b>Unavailable</b>: the trend model is not shown because it has not beaten simple baselines out of sample.</p>
          {ml.validation && (
            <p className="secondary small section">
              Edge over the best baseline: {pp(ml.validation.edge * 100)} (required: {pp(ml.validation.required_edge * 100)}).
            </p>
          )}
          <p className="muted small">{ml.reason}</p>
        </>
      )}
    </div>
  )
}

function History({ rows }: { rows: HistoryRow[] }) {
  if (rows.length < 2) return null
  return (
    <div className="panel section">
      <h2>Past analyses</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Date</th><th>Stance</th><th className="num">Price</th><th className="num">Fair value</th><th className="num">Confidence</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.job_id}>
                <td>{dateLabel(r.created_at)}</td>
                <td>{r.stance ? <StanceBadge stance={r.stance} /> : 'n/a'}</td>
                <td className="num">{money(r.price)}</td>
                <td className="num">{r.fair_value_base ? `${money(r.fair_value_low)} to ${money(r.fair_value_high)}` : 'n/a'}</td>
                <td className="num">{r.confidence ?? 'n/a'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function AnalysisView({ analysis: a, history }: { analysis: Analysis; history: HistoryRow[] }) {
  return (
    <article className="report">
      <Header a={a} />

      {a.conclusion && (
        <div className="card bottom-line">
          <h2>Bottom line</h2>
          <p className="section">{a.conclusion}</p>
        </div>
      )}

      <Verdicts a={a} />
      <FairValueSection a={a} />

      <div className="grid split section">
        <MethodsTable a={a} />
        <Expectations a={a} />
      </div>

      <div className="grid two section">
        <Fundamentals a={a} />
        <News a={a} />
      </div>

      <Market a={a} />
      <Reasons a={a} />

      {a.thesis?.available && (
        <div className="panel section">
          <h2>AI-written thesis</h2>
          <p style={{ whiteSpace: 'pre-line' }}>{a.thesis.text}</p>
          <p className="muted small section">{a.thesis.note}</p>
        </div>
      )}

      <div className="grid two section">
        <Ml a={a} />
        <div className="panel">
          <h2>Data limitations</h2>
          <List items={a.explanation.data_limitations} mark="-" tone="neutral" />
        </div>
      </div>

      <History rows={history} />
    </article>
  )
}
