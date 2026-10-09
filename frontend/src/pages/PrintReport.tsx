import { ArrowLeft, FilePdf, WarningOctagon } from '@phosphor-icons/react'
import { useEffect, useRef, type ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { FairValueChart } from '../components/FairValueChart'
import { StanceBadge } from '../components/Status'
import { TraceBody } from '../components/Traces'
import { StillNumbers } from '../motion/still'
import type { Analysis } from '../lib/api'
import { DISCLAIMER } from '../lib/copy'
import { bareSymbol, snapshotDate } from '../lib/demo'
import { isNum, metricValue, money, num, pct, pp, title } from '../lib/format'
import { type Source, useAnalysis } from '../lib/useAnalysis'

/* A paper version of a report, designed for "Save as PDF": the verdict, the
   reasoning that led to it, and the evidence behind it, in reading order.
   Always printed on white, whatever theme the app uses. The ML trend model
   is left out on purpose: it failed validation and drives nothing. */

const METHODS: [string, string][] = [
  ['dcf', 'DCF'], ['growth_dcf', 'Growth-stage DCF'], ['peer_pe', 'Peer P/E'],
  ['peer_pb', 'Peer P/B'], ['peer_evs', 'Peer EV/Sales'], ['historical_pe', 'Historical P/E'],
]

const today = () => new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })

function Section({ title: heading, children, newPage = false }: { title: string; children: ReactNode; newPage?: boolean }) {
  return (
    <section className={`pr-section${newPage ? ' new-page' : ''}`}>
      <h2>{heading}</h2>
      {children}
    </section>
  )
}

function Bullets({ items, empty = 'None recorded.' }: { items: string[]; empty?: string }) {
  return items.length ? <ul className="pr-list">{items.map((t) => <li key={t}>{t}</li>)}</ul> : <p className="pr-muted">{empty}</p>
}

const EVENT_LABELS: Record<string, string> = { m_and_a: 'M&A', corporate_action: 'Corporate action', earnings: 'Earnings', management: 'Management', regulatory: 'Regulatory', legal: 'Legal', order_win: 'Order win', guidance: 'Guidance' }
const eventLabel = (t: string) => EVENT_LABELS[t] ?? t.charAt(0).toUpperCase() + t.slice(1).replace(/_/g, ' ')
// "News event: [m_and_a] Headline" -> "News event (M&A): Headline"
const cleanTags = (s: string) => s.replace(/:\s*\[([a-z_]+)\]\s*/, (_, t) => ` (${eventLabel(t)}): `).replace(/^\[([a-z_]+)\]\s*/, (_, t) => `${eventLabel(t)}: `)

// "[earnings] Headline - Source" -> type chip + headline
function EventList({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <p className="pr-muted">{empty}</p>
  return (
    <ul className="pr-events">
      {items.map((raw) => {
        const m = raw.match(/^\[([^\]]+)\]\s*(.*)$/)
        return <li key={raw}>{m && <span className="pr-chip">{eventLabel(m[1])}</span>}<span>{m ? m[2] : raw}</span></li>
      })}
    </ul>
  )
}

function Cover({ a, source }: { a: Analysis; source: Source | null }) {
  const fv = a.fair_value
  const v = a.explanation.verdicts
  const asOf = source?.kind === 'snapshot' ? `Snapshot of ${snapshotDate(source.exportedAt)}` : `Live analysis, ${today()}`
  return (
    <header className="pr-cover">
      <div className="pr-brand">Stock Analysis Engine <span>Analysis report</span></div>
      <h1>{a.company_name}</h1>
      <p className="pr-sub">
        {bareSymbol(a.ticker)} on NSE, {a.industry ?? a.sector ?? 'industry n/a'}, analysed as {title(a.company_profile.company_type).toLowerCase()}
      </p>
      <p className="pr-meta">{asOf}. Price {money(a.current_price)}.{a.engine_version ? ` Engine ${a.engine_version}.` : ''}</p>

      <div className="pr-verdict">
        <div className="pr-stance">
          <span className="pr-label">Overall stance</span>
          <StanceBadge stance={a.explanation.stance} />
        </div>
        <dl className="pr-figs">
          <div><dt>Fair value (base)</dt><dd>{fv.available ? money(fv.base) : 'n/a'}</dd><span>{fv.available ? `${money(fv.low)} to ${money(fv.high)}` : fv.reason ?? ''}</span></div>
          <div><dt>Upside to base</dt><dd>{pct(fv.upside_base, true, 0)}</dd><span>{v?.valuation.label ?? ''}</span></div>
          <div><dt>Confidence</dt><dd>{a.confidence.score}/100</dd><span>{a.confidence.label}</span></div>
          <div><dt>Quality</dt><dd>{isNum(a.fundamental_score.score) ? `${Math.round(a.fundamental_score.score)}/100` : 'n/a'}</dd><span>{a.fundamental_score.label}</span></div>
        </dl>
        {v && (
          <p className="pr-split">
            Quality <b>{v.quality}</b>, valuation <b>{v.valuation.label.toLowerCase()}</b>, timing <b>{v.timing.label.toLowerCase()}</b> over the {v.timing.horizon}.
          </p>
        )}
      </div>

      {a.conclusion && (
        <div className="pr-bottom">
          <h2>Bottom line</h2>
          <p>{a.conclusion}</p>
        </div>
      )}
    </header>
  )
}

function Valuation({ a }: { a: Analysis }) {
  const weights = a.fair_value.weights_used ?? {}
  const e = a.expectations
  const sc = a.scenarios
  const sim = a.method_results.growth_dcf?.simulation
  return (
    <>
      <table className="pr-table">
        <thead><tr><th>Method</th><th className="num">Value</th><th className="num">Range</th><th className="num">Weight</th><th>Basis or reason</th></tr></thead>
        <tbody>
          {METHODS.map(([key, label]) => {
            const m = a.method_results[key]
            if (!m) return null
            return (
              <tr key={key} className={m.available ? '' : 'off'}>
                <td>{label}</td>
                <td className="num">{m.available ? money(m.base) : 'n/a'}</td>
                <td className="num">{m.available ? `${money(m.low)} to ${money(m.high)}` : 'n/a'}</td>
                <td className="num">{weights[key] ? `${Math.round(weights[key] * 100)}%` : m.available ? 'context' : 'n/a'}</td>
                <td>{m.available ? m.range_basis : m.reason}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {(a.inputs.risk_premium_reasons ?? []).length > 0 && <p className="pr-note">Discount-rate risk premium: {a.inputs.risk_premium_reasons!.join('; ')}.</p>}

      <div className="pr-cols">
        <div>
          <h3>What today's price assumes</h3>
          {e?.available ? <><p><b>{e.assessment}.</b> {e.summary}</p><p className="pr-muted">{e.method}</p></> : <p className="pr-muted">{e?.reason ?? 'Unavailable.'}</p>}
          {sim && (
            <p className="pr-note">
              {sim.runs.toLocaleString('en-IN')} simulated futures: 10th percentile {money(sim.p10)}, median {money(sim.p50)}, 90th percentile {money(sim.p90)};{' '}
              {Math.round(sim.share_justifying_price * 100)}% justify today's price.
            </p>
          )}
        </div>
        <div>
          <h3>Scenarios{sc?.horizon_years ? ` (${sc.horizon_years} years)` : ''}</h3>
          {sc?.available && sc.cases ? (
            <table className="pr-table compact">
              <thead><tr><th>Case</th><th className="num">Growth</th><th className="num">Exit P/E</th><th className="num">Value</th><th className="num">vs price</th></tr></thead>
              <tbody>
                {['bear', 'base', 'bull'].filter((k) => sc.cases![k]).map((k) => {
                  const c = sc.cases![k]
                  return <tr key={k}><td>{title(k)}</td><td className="num">{pct(c.growth * 100)}</td><td className="num">{num(c.exit_pe, 1)}x</td><td className="num">{money(c.value)}</td><td className="num">{pct(c.upside, true, 0)}</td></tr>
                })}
              </tbody>
            </table>
          ) : <p className="pr-muted">{sc?.reason ?? 'Unavailable.'}</p>}
          {sc?.payoff_summary && <p className="pr-muted">{sc.payoff_summary}</p>}
        </div>
      </div>
    </>
  )
}

function Fundamentals({ a }: { a: Analysis }) {
  const f = a.fundamental_score
  return (
    <>
      <table className="pr-table">
        <thead><tr><th>Metric</th><th className="num">Value</th><th className="num">Score</th><th>Assessment</th><th>Period</th></tr></thead>
        <tbody>
          {f.metrics.map((m) => (
            <tr key={m.key}><td>{m.label}</td><td className="num">{metricValue(m.value, m.unit)}</td><td className="num">{Math.round(m.score)}/100</td><td>{m.assessment}</td><td>{m.source ?? 'n/a'}</td></tr>
          ))}
        </tbody>
      </table>
      {f.missing.length > 0 && <p className="pr-note">Unavailable: {f.missing.join(', ')}.</p>}
    </>
  )
}

function Market({ a }: { a: Analysis }) {
  const c = a.market_context
  const rows: [string, string][] = [
    ['Stock, 30 days', pct(c.stock_return)], ['NIFTY, 30 days', pct(c.market_return)], ['Relative to NIFTY', pp(c.relative_to_market)],
    [`Sector (${a.sector_benchmark?.name ?? 'n/a'}), 30 days`, pct(c.sector_return)], ['Relative to sector', pp(c.relative_to_sector)],
    ['RSI (14)', num(a.latest_technical?.RSI_14, 1)], ['Beta vs NIFTY', num(a.beta)], ['Trend', a.technical_score.label],
  ]
  return (
    <div className="pr-cols">
      <dl className="pr-kv">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
      <div>
        <h3>Signals behind the timing verdict</h3>
        <ul className="pr-list">{a.technical_score.signals.map(([s, t]) => <li key={t}>{s > 0 ? 'Positive' : 'Negative'}: {t}</li>)}</ul>
        {(a.explanation.verdicts?.timing.notes ?? []).map((n) => <p key={n} className="pr-note">{n}</p>)}
      </div>
    </div>
  )
}

function News({ a }: { a: Analysis }) {
  const n = a.news
  const e = n.events
  return (
    <>
      <dl className="pr-kv wide">
        <div><dt>Sentiment</dt><dd>{n.label ?? 'n/a'}{isNum(n.news_score) ? ` (${Math.round(n.news_score)}/100)` : ''}</dd></div>
        <div><dt>FinBERT score</dt><dd>{isNum(n.finbert_score) ? n.finbert_score.toFixed(2) : 'n/a'} (-1 to +1)</dd></div>
        <div><dt>Headlines read</dt><dd>{n.raw_article_count ?? 'n/a'}, {n.duplicates_removed ?? 0} duplicates removed</dd></div>
        <div><dt>Material events</dt><dd>{isNum(e?.material_share) ? `${Math.round(e!.material_share! * 100)}% of headlines` : 'n/a'}</dd></div>
      </dl>
      {n.sentiment_basis && <p className="pr-note">Sentiment scored on {n.sentiment_basis}.</p>}
      {e ? (
        <div className="pr-cols">
          <div><h3>Catalysts</h3><EventList items={e.catalysts} empty="No material positive events." /></div>
          <div><h3>Event risks</h3><EventList items={e.risks} empty="No material negative events." /></div>
        </div>
      ) : <p className="pr-muted">Event tagging was not run for this analysis (local AI model unavailable or news switched off).</p>}
      {(e?.other_material ?? []).length > 0 && <><h3>Other material events</h3><EventList items={e!.other_material!} empty="" /></>}
      {e?.accuracy_note && <p className="pr-note">{e.accuracy_note}</p>}
      {(n.warnings ?? []).length > 0 && <p className="pr-note">Notes: {n.warnings!.join('; ')}.</p>}
    </>
  )
}

function Confidence({ a }: { a: Analysis }) {
  return (
    <>
      {(a.confidence.components ?? []).length > 0 && (
        <table className="pr-table">
          <thead><tr><th>Check</th><th className="num">Points</th><th>Why</th></tr></thead>
          <tbody>
            {a.confidence.components!.map((c) => (
              <tr key={c.name}><td>{c.name}</td><td className="num">{Math.round(c.points)} / {c.max}</td><td>{[...c.positives, ...c.concerns].join('; ') || 'n/a'}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><td>Total</td><td className="num">{a.confidence.score} / 100</td><td>{a.confidence.label}</td></tr></tfoot>
        </table>
      )}
    </>
  )
}

export function PrintReportPage() {
  const { ticker = '' } = useParams()
  const [params] = useSearchParams()
  const symbol = bareSymbol(ticker)
  const state = useAnalysis(symbol, true, 0)
  const printed = useRef(false)
  const a = state.analysis

  // Name the PDF after the company and date; open the print dialog once ready.
  useEffect(() => {
    if (!a) return
    const previous = document.title
    document.title = `${bareSymbol(a.ticker)} analysis report ${new Date().toISOString().slice(0, 10)}`
    if (!printed.current && params.get('print') !== '0') {
      printed.current = true
      document.fonts.ready.then(() => setTimeout(() => window.print(), 400))
    }
    return () => { document.title = previous }
  }, [a, params])

  return (
    <div className="pr-shell">
      <div className="pr-toolbar">
        <Link className="btn btn-ghost" to={`/s/${symbol}`}><ArrowLeft size={16} />Back to the report</Link>
        <button type="button" className="btn btn-primary" onClick={() => window.print()} disabled={!a}>
          <FilePdf size={18} weight="fill" />Save as PDF
        </button>
        <span className="pr-hint">In the print dialog, choose "Save as PDF" as the destination.</span>
      </div>

      {state.status === 'error' && (
        <p className="pr-error"><WarningOctagon size={18} /> Could not load {symbol}: {state.error}</p>
      )}
      {state.status === 'loading' && <p className="pr-loading">Preparing the report for {symbol}…</p>}

      {a && (
        <StillNumbers.Provider value>
        <article className="paper">
          <Cover a={a} source={state.source} />

          {a.fair_value.available && (
            <Section title="Fair value against today's price">
              <FairValueChart fairValue={a.fair_value} price={a.current_price} consensus={a.inputs.consensus_target}
                growthRange={a.method_results.growth_dcf?.simulation ? { p10: a.method_results.growth_dcf.simulation.p10, p90: a.method_results.growth_dcf.simulation.p90 } : null} />
            </Section>
          )}

          <Section title="How the stance was decided" newPage>
            <TraceBody trace={{ type: 'stance' }} a={a} onJump={() => {}} />
          </Section>

          <Section title="How the fair value was built">
            <TraceBody trace={{ type: 'fairvalue' }} a={a} onJump={() => {}} />
          </Section>

          <Section title="What would change the verdict">
            <Bullets items={a.explanation.verdicts?.triggers ?? []} empty="No price triggers for this verdict." />
          </Section>

          <Section title="Valuation in detail">
            <Valuation a={a} />
          </Section>

          <Section title="Fundamentals">
            <Fundamentals a={a} />
          </Section>

          <Section title="The case, both ways">
            <div className="pr-cols">
              <div><h3>Bull case</h3><Bullets items={a.explanation.why_bullish} /></div>
              <div><h3>Bear case</h3><Bullets items={a.explanation.why_not_bullish} /></div>
            </div>
            <h3>Key risks</h3>
            <Bullets items={a.explanation.risks.map(cleanTags)} />
          </Section>

          <Section title="News and sentiment">
            <News a={a} />
          </Section>

          {a.thesis?.available && a.thesis.text && (
            <Section title="AI-written thesis">
              <p className="pr-thesis">{a.thesis.text}</p>
              {a.thesis.note && <p className="pr-note">{a.thesis.note}</p>}
            </Section>
          )}

          <Section title="Market context">
            <Market a={a} />
          </Section>

          <Section title="How far to trust this analysis">
            <Confidence a={a} />
            <h3>Data limitations</h3>
            <Bullets items={a.explanation.data_limitations} />
          </Section>

          <Section title="Method and disclaimer">
            <p className="pr-note">
              Fair value blends independent methods chosen for this type of business (core methods only; context methods
              never move the base). Quality, valuation and timing are judged separately; safety gates come before any
              stance. News is read by FinBERT for sentiment and by a local language model that separates material
              company events from noise. Figures are labelled with their period; data from Yahoo Finance and NSE;
              amounts in rupees.
            </p>
            <p className="pr-disclaimer">{DISCLAIMER}</p>
          </Section>
        </article>
        </StillNumbers.Provider>
      )}
    </div>
  )
}
