import { ArrowRight, CheckCircle, MinusCircle, XCircle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import type { Analysis } from '../lib/api'
import { assessmentTone, crore, isNum, metricValue, money, num, pct, title } from '../lib/format'
import { StanceBadge } from './Status'
import { CountUp } from '../motion/CountUp'
import { METHOD_INFO, METRIC_INFO, type TabTarget, type Trace, humanKey, traceHeading } from '../lib/traces'

/* "How we got here" pages. Each trace replays the engine's own decision
   path for one headline number, step by step, using the values in the
   analysis payload. Thresholds mirror src/config.py and src/explain.py. */


const T = {
  minConfidence: 35, attractiveConfidence: 50, attractiveUpside: 15, avoidUpside: -15,
  attractiveQuality: 55, weakQuality: 40, strongQuality: 70, consensusGate: 3, minAnalysts: 5, fairBand: 0.14,
}



type State = 'pass' | 'stop' | 'skip' | 'info'

function Step({ n, heading, state = 'info', result, children }: {
  n: number | string; heading: string; state?: State; result?: boolean; children?: ReactNode
}) {
  const Icon = state === 'pass' ? CheckCircle : state === 'stop' ? XCircle : state === 'skip' ? MinusCircle : null
  return (
    <li className={`step ${state}${result ? ' result' : ''}`}>
      <span className="dot" aria-hidden="true">{Icon ? <Icon size={14} weight="bold" /> : n}</span>
      <div className="step-body">
        <h3>{heading}{state === 'stop' && <span className="visually-hidden"> (decided here)</span>}</h3>
        {children}
      </div>
    </li>
  )
}

const Formula = ({ children }: { children: ReactNode }) => <div className="formula">{children}</div>

function Bar({ value, max = 100, tone }: { value: number; max?: number; tone?: string }) {
  return <div className={`meter ${tone ?? ''}`} aria-hidden="true"><span style={{ width: `${Math.max(2, (value / max) * 100)}%` }} /></div>
}

function assumptionValue(key: string, v: unknown): string {
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (typeof v === 'string') return v
  if (!isNum(v)) return 'n/a'
  if (/growth|wacc|cost|premium|margin|rate/i.test(key) && Math.abs(v) < 1) return pct(v * 100, false)
  if (Math.abs(v) >= 1e7) return crore(v)
  return num(v, 2)
}

/* ---------- stance ---------- */

function StanceTrace({ a }: { a: Analysis }) {
  const fv = a.fair_value
  const c = a.confidence.score
  const q = a.fundamental_score.score
  const p = a.company_profile
  const u = fv.upside_base
  const stance = a.explanation.stance
  const consensus = a.inputs.consensus_target
  const analysts = a.inputs.analyst_count ?? 0
  const ratio = fv.available && isNum(fv.base) && isNum(consensus) && consensus > 0 ? fv.base / consensus : null

  const gates: { heading: string; ok: boolean; detail: string }[] = [
    { heading: 'Enough data to judge', ok: fv.available && c >= T.minConfidence,
      detail: `Fair value ${fv.available ? 'available' : 'unavailable'}; confidence ${c}/100 (needs ${T.minConfidence}+).` },
    { heading: 'Earnings are usable', ok: !(p.valuation_family === 'operating' && p.earnings_usable === false) && !p.holding_company,
      detail: p.holding_company ? 'Holding company: needs a sum-of-the-parts valuation.' : 'Loss-making companies get "what the price requires" instead of a verdict.' },
    { heading: 'Model agrees with the street within 3x', ok: !(ratio && analysts >= T.minAnalysts && (ratio > T.consensusGate || ratio < 1 / T.consensusGate)),
      detail: ratio && analysts >= T.minAnalysts ? `Model base is ${num(ratio)}x the consensus of ${analysts} analysts.` : 'Too few analysts to check; gate skipped.' },
    { heading: 'At least two valuation methods', ok: fv.methods_used.length >= 2,
      detail: `Used: ${fv.methods_used.join(', ') || 'none'}.` },
  ]
  const failedAt = gates.findIndex((g) => !g.ok)

  const rules: { heading: string; match: boolean; result: string; detail: string }[] = isNum(u) ? [
    { heading: `Upside at or below ${T.avoidUpside}%`, match: u <= T.avoidUpside,
      result: isNum(q) && q >= T.strongQuality ? 'WATCH' : 'AVOID',
      detail: `Upside ${pct(u)}. Strong businesses (quality ${T.strongQuality}+) get WATCH: peers often understate a deserved premium.` },
    { heading: `Weak quality (under ${T.weakQuality}) without ${T.attractiveUpside}% upside`, match: isNum(q) && q < T.weakQuality && u < T.attractiveUpside,
      result: 'AVOID', detail: `Quality ${isNum(q) ? Math.round(q) : 'n/a'}/100, upside ${pct(u)}.` },
    { heading: `Upside ${T.attractiveUpside}%+, quality ${T.attractiveQuality}+, confidence ${T.attractiveConfidence}+`,
      match: u >= T.attractiveUpside && isNum(q) && q >= T.attractiveQuality && c >= T.attractiveConfidence,
      result: 'ATTRACTIVE', detail: `Upside ${pct(u)}, quality ${isNum(q) ? Math.round(q) : 'n/a'}, confidence ${c}.` },
    { heading: 'Otherwise', match: true, result: 'WATCH', detail: 'Nothing decisive either way.' },
  ] : []
  const firstRule = rules.findIndex((r) => r.match)

  let n = 0
  return (
    <>
      <p className="secondary">The stance runs through four safety gates, then four rules in order. The first rule that matches decides.</p>
      <ol className="trace">
        {gates.map((g, i) => (
          <Step key={g.heading} n={++n} heading={g.heading}
            state={failedAt === -1 || i < failedAt ? 'pass' : i === failedAt ? 'stop' : 'skip'}>
            <p className="small secondary">{g.detail}</p>
          </Step>
        ))}
        {failedAt === -1 && rules.map((r, i) => (
          <Step key={r.heading} n={++n} heading={r.heading} state={i < firstRule ? 'skip' : i === firstRule ? 'stop' : 'skip'}>
            <p className="small secondary">{r.detail}{i === firstRule ? ` Result: ${r.result}.` : ''}</p>
          </Step>
        ))}
        <Step n="=" heading="Stance" result>
          <StanceBadge stance={stance} />
        </Step>
      </ol>
    </>
  )
}

/* ---------- fair value ---------- */

function FairValueTrace({ a }: { a: Analysis }) {
  const fv = a.fair_value
  const weights = fv.weights_used ?? {}
  const excluded = a.valuation_selection?.excluded_methods ?? {}
  const rows = Object.entries(weights).map(([key, w]) => ({ key, w, m: a.method_results[key] }))
  const total = rows.reduce((s, r) => s + (r.m?.base ?? 0) * r.w, 0)

  if (!fv.available) return <p className="secondary">{fv.reason ?? 'No fair value could be produced.'}</p>

  return (
    <ol className="trace">
      <Step n={1} heading="Classify the company">
        <p className="small secondary">Analysed as <b>{title(a.company_profile.company_type).toLowerCase()}</b>
          {a.company_profile.classification_certainty ? ` (${a.company_profile.classification_certainty.toLowerCase()} certainty)` : ''}. The type decides which methods are valid.</p>
      </Step>
      <Step n={2} heading="Choose the methods">
        <ul className="chips">
          {fv.methods_used.map((m) => <li key={m} className="chip on">{m}</li>)}
          {Object.keys(excluded).map((m) => <li key={m} className="chip off" title={excluded[m]}>{METHOD_INFO[m]?.name ?? humanKey(m)}</li>)}
        </ul>
        {Object.keys(excluded).length > 0 && <p className="muted small" style={{ marginTop: 8 }}>Greyed methods were excluded. Hover them for the reason.</p>}
      </Step>
      <Step n={3} heading="Value the company with each method">
        <div className="contrib">
          {rows.map(({ key, w, m }) => (
            <div key={key} className="contrib-row">
              <span>{METHOD_INFO[key]?.name ?? humanKey(key)}</span>
              <span className="mono">{money(m?.base)}</span>
              <span className="mono muted">x {Math.round(w * 100)}%</span>
              <span className="mono">{money((m?.base ?? 0) * w)}</span>
            </div>
          ))}
        </div>
      </Step>
      <Step n={4} heading="Blend by weight">
        <Formula>{rows.map((r, i) => <span key={r.key}>{i > 0 && ' + '}{money((r.m?.base ?? 0) * r.w)}</span>)} = <b><CountUp value={total} format={money} delay={0.25} /></b></Formula>
        <p className="muted small">Weights favour methods that suit this company type and agree with the others.</p>
      </Step>
      <Step n={5} heading="Build the range">
        <p className="small secondary">
          From each method's own low and high case: {money(fv.low)} to {money(fv.high)}.
          {fv.widened_for_disagreement && ` Widened because the methods disagree (spread ${pct((fv.dispersion?.coefficient_of_variation ?? 0) * 100, false, 0)}).`}
        </p>
      </Step>
      <Step n="=" heading="Fair value (base)" result>
        <div className="big-num">{isNum(fv.base) ? <CountUp value={fv.base} format={money} delay={0.3} /> : 'n/a'}</div>
        <p className="muted small">Range {money(fv.low)} to {money(fv.high)}</p>
      </Step>
    </ol>
  )
}

function UpsideTrace({ a }: { a: Analysis }) {
  const fv = a.fair_value
  const v = a.explanation.verdicts?.valuation
  return (
    <ol className="trace">
      <Step n={1} heading="Start from the blended fair value"><div className="big-num sm">{money(fv.base)}</div></Step>
      <Step n={2} heading="Compare with the last traded price"><div className="big-num sm">{money(a.current_price)}</div></Step>
      <Step n={3} heading="Upside = fair value / price - 1">
        <Formula>{money(fv.base)} / {money(a.current_price)} - 1 = <b>{isNum(fv.upside_base) ? <CountUp value={fv.upside_base} format={(n) => pct(n)} delay={0.2} /> : 'n/a'}</b></Formula>
        <p className="muted small">Across the range: {pct(fv.upside_low)} (low) to {pct(fv.upside_high)} (high).</p>
      </Step>
      {v && (
        <Step n={4} heading="Turn the gap into a label">
          <p className="small secondary">The engine uses the log gap so +50% and -33% count as equally far. {v.measure ? `Here: ${v.measure}.` : ''}</p>
        </Step>
      )}
      <Step n="=" heading="Valuation verdict" result><span className="stance neutral">{v?.label ?? 'n/a'}</span></Step>
    </ol>
  )
}

function ConfidenceTrace({ a }: { a: Analysis }) {
  const parts = a.confidence.components ?? []
  return (
    <>
      <p className="secondary">Confidence measures how much to trust the numbers, not whether the stock is good. Each check earns points.</p>
      <ol className="trace">
        {parts.map((c, i) => (
          <Step key={c.name} n={i + 1} heading={`${c.name}: ${Math.round(c.points)} of ${c.max}`}>
            <Bar value={c.points} max={c.max} tone={c.points / c.max >= 0.75 ? 'good' : c.points / c.max >= 0.45 ? 'warn' : 'bad'} />
            {[...c.positives.map((t) => ['+', t]), ...c.concerns.map((t) => ['-', t])].map(([s, t]) => (
              <p key={t} className="small secondary" style={{ marginTop: 6 }}><span className={s === '+' ? 'up-ink' : 'down-ink'}>{s}</span> {t}</p>
            ))}
          </Step>
        ))}
        <Step n="=" heading="Confidence" result>
          <div className="big-num"><CountUp value={a.confidence.score} format={(n) => String(Math.round(n))} delay={0.3} /><span className="muted small">/100</span></div>
          <p className="muted small">{a.confidence.label}</p>
        </Step>
      </ol>
    </>
  )
}

function QualityTrace({ a }: { a: Analysis }) {
  const f = a.fundamental_score
  return (
    <>
      <p className="secondary">Each metric is scored 0 to 100 against Indian peers of the same type, then combined.</p>
      <ol className="trace">
        {f.metrics.map((m, i) => (
          <Step key={m.key} n={i + 1} heading={`${m.label}: ${metricValue(m.value, m.unit)}`}>
            <Bar value={m.score} tone={assessmentTone(m.assessment)} />
            <p className="muted small" style={{ marginTop: 4 }}>{m.assessment}, {Math.round(m.score)}/100{m.source ? `. ${m.source}` : ''}</p>
          </Step>
        ))}
        <Step n="=" heading="Quality score" result>
          <div className="big-num">{isNum(f.score) ? <CountUp value={f.score} format={(n) => String(Math.round(n))} delay={0.3} /> : 'n/a'}<span className="muted small">/100</span></div>
          <p className="muted small">{f.label}. {T.strongQuality}+ is strong, under {T.weakQuality} is weak.</p>
        </Step>
      </ol>
    </>
  )
}

function TimingTrace({ a }: { a: Analysis }) {
  const t = a.technical_score
  return (
    <>
      <p className="secondary">Timing reads the trend over the {a.explanation.verdicts?.timing.horizon ?? 'next few weeks'}. It never changes the valuation.</p>
      <ol className="trace">
        {t.signals.map(([s, text], i) => (
          <Step key={text} n={i + 1} heading={text} state={s > 0 ? 'pass' : 'stop'} />
        ))}
        <Step n="=" heading="Trend" result>
          <div className="big-num sm">{t.label}</div>
          <p className="muted small">{t.signals.filter(([s]) => s > 0).length} positive and {t.signals.filter(([s]) => s < 0).length} negative signals.</p>
        </Step>
      </ol>
    </>
  )
}

function MethodTrace({ a, k }: { a: Analysis; k: string }) {
  const m = a.method_results[k]
  const info = METHOD_INFO[k]
  const weight = a.fair_value.weights_used?.[k]
  if (!m) return null
  const assumptions = Object.entries(m.assumptions ?? {}).filter(([, v]) => ['number', 'string', 'boolean'].includes(typeof v))
  return (
    <>
      <p className="secondary">{info?.what}</p>
      <ol className="trace">
        {assumptions.length > 0 && (
          <Step n={1} heading="Inputs">
            <dl className="kv">{assumptions.map(([key, v]) => <div key={key}><dt>{humanKey(key)}</dt><dd>{assumptionValue(key, v)}</dd></div>)}</dl>
          </Step>
        )}
        {isNum(m.multiple_median) && (
          <Step n={assumptions.length ? 2 : 1} heading={`Peer multiples (${m.peer_count ?? 'n/a'} peers)`}>
            <Formula>25th pct {num(m.multiple_low, 1)}x, median <b>{num(m.multiple_median, 1)}x</b>, 75th pct {num(m.multiple_high, 1)}x</Formula>
          </Step>
        )}
        <Step n="=" heading={m.available ? 'Value per share' : 'Not used'} result>
          {m.available ? (
            <>
              <div className="big-num">{isNum(m.base) ? <CountUp value={m.base} format={money} delay={0.2} /> : 'n/a'}</div>
              <p className="muted small">Range {money(m.low)} to {money(m.high)} ({m.range_basis}). {weight ? `Weight in the blend: ${Math.round(weight * 100)}%.` : 'Not part of the blend.'}</p>
            </>
          ) : <p className="small secondary">{m.reason}</p>}
        </Step>
      </ol>
    </>
  )
}

function MetricTrace({ a, k }: { a: Analysis; k: string }) {
  const m = a.fundamental_score.metrics.find((x) => x.key === k)
  if (!m) return null
  return (
    <>
      <p className="secondary">{METRIC_INFO[k] ?? 'A fundamental measure scored against peers.'}</p>
      <ol className="trace">
        <Step n={1} heading="Reported value"><div className="big-num sm">{metricValue(m.value, m.unit)}</div><p className="muted small">{m.source ?? 'Period n/a'}</p></Step>
        <Step n={2} heading="Scored against peers of the same type">
          <Bar value={m.score} tone={assessmentTone(m.assessment)} />
          <p className="muted small" style={{ marginTop: 4 }}>{Math.round(m.score)}/100</p>
        </Step>
        <Step n="=" heading="Assessment" result><span className={`stance ${assessmentTone(m.assessment)}`}>{m.assessment}</span></Step>
      </ol>
    </>
  )
}


const TAB_LABEL: Record<TabTarget, string> = {
  overview: 'Overview', valuation: 'Valuation', fundamentals: 'Fundamentals', market: 'Market', news: 'News and risks',
}

export function TraceBody({ trace, a, onJump }: { trace: Trace; a: Analysis; onJump: (tab: TabTarget) => void }) {
  const { tab } = traceHeading(trace, a)
  return (
    <div className="stack">
      {trace.type === 'stance' && <StanceTrace a={a} />}
      {trace.type === 'fairvalue' && <FairValueTrace a={a} />}
      {trace.type === 'upside' && <UpsideTrace a={a} />}
      {trace.type === 'confidence' && <ConfidenceTrace a={a} />}
      {trace.type === 'quality' && <QualityTrace a={a} />}
      {trace.type === 'timing' && <TimingTrace a={a} />}
      {trace.type === 'method' && <MethodTrace a={a} k={trace.key} />}
      {trace.type === 'metric' && <MetricTrace a={a} k={trace.key} />}
      <button type="button" className="btn btn-secondary" onClick={() => onJump(tab)} style={{ justifySelf: 'start' }}>
        Open the {TAB_LABEL[tab]} section <ArrowRight size={16} />
      </button>
    </div>
  )
}
