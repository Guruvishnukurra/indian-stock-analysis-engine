import { CheckCircle, Info, XCircle } from '@phosphor-icons/react'
import { useEffect, useState, type ReactNode } from 'react'
import { ConsensusRows, GoldenGrid, MlChart, MlSummary, NewsBars, PeerBars } from '../components/story/EvidenceCharts'
import { StoryShell } from '../components/story/StoryShell'
import { SlideIndicator } from '../motion/SlideIndicator'
import { type Evidence, type GoldenRow, loadEvidence, loadGolden, typicalMiss } from '../lib/evidence'

const SECTIONS = [
  { id: 'ml', label: 'ML trend model' },
  { id: 'news', label: 'News tagging' },
  { id: 'peers', label: 'Peer selection' },
  { id: 'consensus', label: 'Analyst consensus' },
  { id: 'golden', label: 'Golden set' },
]

const pc = (v: number, digits = 0) => `${(v * 100).toFixed(digits)}%`

// pass / fail are test outcomes; info states a property without grading it.
function Verdict({ pass, info = false, children }: { pass?: boolean; info?: boolean; children: ReactNode }) {
  const tone = info ? 'info' : pass ? 'pass' : 'fail'
  const Icon = info ? Info : pass ? CheckCircle : XCircle
  return (
    <p className={`ev-verdict ${tone}`}>
      <Icon size={18} weight="fill" aria-hidden="true" />
      <span>{children}</span>
    </p>
  )
}

function Section({ id, heading, children }: { id: string; heading: string; children: ReactNode }) {
  return (
    <section id={id} className="ev-section" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}>{heading}</h2>
      {children}
    </section>
  )
}

function Toggle<T extends string>({ label, options, value, onChange }: {
  label: string; options: { id: T; label: string }[]; value: T; onChange: (v: T) => void
}) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      <SlideIndicator index={options.findIndex((o) => o.id === value)} className="seg-pill" kind="pill" />
      {options.map((o) => (
        <button key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)}>{o.label}</button>
      ))}
    </div>
  )
}

export function EvidencePage() {
  const [data, setData] = useState<{ evidence: Evidence; source: 'live' | 'export' } | null>(null)
  const [golden, setGolden] = useState<Record<string, GoldenRow>>({})
  const [newsSet, setNewsSet] = useState<'test' | 'test2'>('test')
  const [peerKind, setPeerKind] = useState<'PE' | 'PB'>('PE')
  const [active, setActive] = useState('ml')

  useEffect(() => {
    loadEvidence().then(setData).catch(() => setData(null))
    loadGolden().then(setGolden)
  }, [])

  useEffect(() => {
    if (!data) return
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setActive(e.target.id)
    }, { rootMargin: '-30% 0px -60% 0px' })
    SECTIONS.forEach((s) => { const el = document.getElementById(s.id); if (el) io.observe(el) })
    return () => io.disconnect()
  }, [data])

  const e = data?.evidence
  const ml = e?.ml_trend
  const news = newsSet === 'test' ? e?.news_events_test : e?.news_events_test2 ?? e?.news_events_test
  const peers = e?.peer_selection
  const cons = e?.consensus_comparison
  const goldenCount = Object.keys(golden).length

  return (
    <StoryShell mainId="evidence-main">
      <header className="page-head">
        <h1>Checked, including what failed.</h1>
        <p className="page-lead">
          Every claim the engine makes is tested against data it was not tuned on. These are the results as the
          validation scripts last wrote them{data ? (data.source === 'live' ? ', read live from the API' : ', from the exported copy') : ''}.
          Each one can be reproduced from a script in the repository.
        </p>
      </header>

      {!e ? (
        <div className="story-loading" aria-busy="true">Loading the validation results</div>
      ) : (
        <div className="ev-layout">
          <nav className="ev-toc" aria-label="On this page">
            <ol>
              {SECTIONS.map((s) => (
                <li key={s.id}><a href={`#${s.id}`} aria-current={active === s.id ? 'true' : undefined}>{s.label}</a></li>
              ))}
            </ol>
          </nav>

          <div className="ev-column">
            {ml && (
              <Section id="ml" heading="The trend model did not earn its place, so it is hidden">
                <p>
                  A model predicting the stock's direction over the next {ml.horizon_trading_days} trading days was trained
                  walk-forward on {ml.n_stocks} stocks ({ml.n_samples.toLocaleString('en-IN')} samples): each year is predicted
                  using only earlier years. To be shown in reports it had to beat the best simple baseline by{' '}
                  {(ml.gate.required_edge * 100).toFixed(0)} percentage points of balanced accuracy.
                </p>
                <Verdict pass={ml.gate.passed}>
                  Best model: {pc(ml.summary[ml.gate.best_model].balanced_accuracy, 1)} against a{' '}
                  {pc(ml.summary[ml.gate.best_baseline].balanced_accuracy, 1)} baseline. An edge of {(ml.gate.edge * 100).toFixed(1)} percentage points,{' '}
                  {ml.gate.passed ? 'which clears the bar.' : `short of the ${(ml.gate.required_edge * 100).toFixed(0)} required. Reports say "unavailable" instead.`}
                </Verdict>
                <figure className="ev-figure scope-light">
                  <MlChart ml={ml} />
                  <figcaption>Balanced accuracy per test year. The shaded zone is where a model would have to sit to be shown.</figcaption>
                </figure>
                <figure className="ev-figure scope-light">
                  <MlSummary ml={ml} />
                  <figcaption>Overall balanced accuracy, all test years. Three classes, so a coin-flip equivalent is 33.3%.</figcaption>
                </figure>
                <h3>Caveats the result carries</h3>
                <ul className="ev-list">{ml.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
              </Section>
            )}

            {news && (
              <Section id="news" heading="News tagging is precise, but misses about half of events">
                <p>
                  A local language model reads each headline and decides whether it is a material company event (results,
                  orders, regulatory action) or noise. A second pass verifies every event it reports. Tested on two
                  held-out sets of {news.n_headlines} headlines each.
                </p>
                <Verdict pass={news.llm_verified.material_precision >= 0.8}>
                  With verification, {pc(news.llm_verified.material_precision)} of reported events on this set are genuine,
                  against {pc(news.keyword_baseline.material_precision)} for keyword rules. Recall is{' '}
                  {pc(news.llm_verified.material_recall)}: the dashboard says so next to every news list.
                </Verdict>
                <Toggle label="Test set" value={newsSet} onChange={setNewsSet}
                  options={[{ id: 'test', label: 'Test set 1' }, { id: 'test2', label: 'Test set 2' }]} />
                <figure className="ev-figure scope-light">
                  <NewsBars test={news} />
                  <figcaption>
                    {news.n_headlines} headlines, model {news.model}. Labels were drafted with an AI assistant and {news.human_checked} of {news.n_headlines} have been human-checked so far.
                  </figcaption>
                </figure>
              </Section>
            )}

            {peers && (
              <Section id="peers" heading="Choosing peers by business, not just size">
                <p>
                  Peer multiples are only as good as the peers. Each selection rule was tested by predicting every
                  company's own multiple from its peers' median and measuring the typical miss.
                </p>
                <Verdict pass>
                  The rule the engine uses (same ownership, ranked by business-description similarity, ignoring companies
                  under 20% of the target's size) cuts the typical P/E miss from {pc(typicalMiss(peers.PE.market_cap.median_abs_log_error))} to{' '}
                  {pc(typicalMiss(peers.PE['floor_0.20'].median_abs_log_error))}.
                </Verdict>
                <Toggle label="Multiple" value={peerKind} onChange={setPeerKind}
                  options={[{ id: 'PE', label: 'Price to earnings' }, { id: 'PB', label: 'Price to book' }]} />
                <figure className="ev-figure scope-light">
                  <PeerBars rows={peers[peerKind]} />
                  <figcaption>Typical miss (median absolute error) predicting each company's {peerKind === 'PE' ? 'P/E' : 'P/B'} from its peers, {Object.values(peers[peerKind])[0].companies} companies. Lower is better.</figcaption>
                </figure>
              </Section>
            )}

            {cons && (
              <Section id="consensus" heading="The engine is not a copy of analyst consensus">
                <p>
                  Consensus is a sanity reference, never an input. Across {cons.all.companies} companies ({cons.universe}),
                  the engine's base value sits a median {pc(Math.abs(cons.all.median_engine_vs_consensus))}{' '}
                  {cons.all.median_engine_vs_consensus < 0 ? 'below' : 'above'} consensus, and consensus falls inside the
                  engine's range for {pc(cons.all.consensus_inside_engine_range)} of them.
                </p>
                <Verdict info>
                  Rank correlation of upside with consensus: {cons.upside_rank_correlation.toFixed(3)}. The engine's
                  relative calls are independent of analysts', which is what an independent check should look like.
                </Verdict>
                <figure className="ev-figure scope-light">
                  <ConsensusRows rows={cons.by_company_type} />
                  <figcaption>Median gap between the engine's base value and consensus, by company type. Orange: engine below consensus.</figcaption>
                </figure>
              </Section>
            )}

            {goldenCount > 0 && (
              <Section id="golden" heading={`${goldenCount} reference companies, re-checked after every change`}>
                <p>
                  The golden set spans sectors and business types. After every engine change a script checks each company's
                  routing, methods and allowed verdicts, then reports what moved. Select any company to open its report.
                </p>
                <GoldenGrid golden={golden} />
              </Section>
            )}
          </div>
        </div>
      )}
    </StoryShell>
  )
}
