import { ArrowRight, ArrowUpRight, MagnifyingGlass } from '@phosphor-icons/react'
import { motion, useInView, useReducedMotion } from 'motion/react'
import { Suspense, lazy, useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { FanCanvas } from '../components/home/FanCanvas'
import { TraceBody } from '../components/Traces'
import type { Analysis } from '../lib/api'
import { type DemoItem, bareSymbol, getManifest, loadSnapshot, realisedVolatility, snapshotDate } from '../lib/demo'
import { money } from '../lib/format'
import { StoryShell } from '../components/story/StoryShell'

const FuturesStage = lazy(() => import('../components/FuturesStage'))

const FALLBACK: DemoItem[] = [
  ['TCS', 'IT services, steady compounder'], ['HDFCBANK', 'Private bank'], ['ATHERENERG', 'Loss-making EV maker'],
  ['TATASTEEL', 'Cyclical metals'], ['BAJFINANCE', 'Consumer lender (NBFC)'], ['WAAREEENER', 'Capex-heavy solar'],
].map(([symbol, description]) => ({ symbol, ticker: `${symbol}.NS`, description, exported_at: '' }))

const DEFAULT_SIGMA = 0.3
const EASE = [0.16, 1, 0.3, 1] as const

/* One authored entrance: the hero copy settles in while the fan draws out. */
function Rise({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 18, filter: 'blur(6px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }} transition={{ duration: 0.9, delay, ease: EASE }}>
      {children}
    </motion.div>
  )
}

function SearchField({ id, inputRef, size = 'lg' }: { id: string; inputRef?: React.Ref<HTMLInputElement>; size?: 'lg' | 'md' }) {
  const navigate = useNavigate()
  const [value, setValue] = useState('')
  const [invalid, setInvalid] = useState(false)
  return (
    <form className={`hero-search ${size}`} role="search" onSubmit={(e) => {
      e.preventDefault()
      const clean = bareSymbol(value)
      if (!/^[A-Z0-9&-]{1,20}$/.test(clean)) { setInvalid(true); return }
      navigate(`/s/${clean}`)
    }}>
      <MagnifyingGlass size={22} aria-hidden="true" />
      <label htmlFor={id} className="visually-hidden">NSE ticker</label>
      <input id={id} ref={inputRef} value={value} onChange={(e) => { setValue(e.target.value); setInvalid(false) }}
        placeholder="Ticker, e.g. TCS" autoComplete="off" spellCheck={false}
        aria-invalid={invalid || undefined} aria-describedby={invalid ? `${id}-err` : undefined} />
      <button type="submit" className="hero-go">Analyse<ArrowRight size={18} weight="bold" aria-hidden="true" /></button>
      {invalid && <span id={`${id}-err`} className="hero-err" role="alert">Enter a ticker such as TCS or HDFCBANK.</span>}
    </form>
  )
}

function Picks({ items, onPreview }: { items: DemoItem[]; onPreview?: (item: DemoItem | null) => void }) {
  return (
    <ul className="picks" aria-label="Showcase companies">
      {items.map((item) => (
        <li key={item.symbol}>
          <Link to={`/s/${item.symbol}`} className="pick-chip"
            onMouseEnter={() => onPreview?.(item)} onFocus={() => onPreview?.(item)}
            onMouseLeave={() => onPreview?.(null)} onBlur={() => onPreview?.(null)}>
            <span className="sym">{item.symbol}</span>
            <span className="desc">{item.description}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Window({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`window scope-dark ${className}`}>
      <div className="window-bar"><span className="window-title">{title}</span></div>
      {children}
    </div>
  )
}

/* Replays one real trace from a snapshot when it scrolls into view. */
function ExplainDemo({ items }: { items: DemoItem[] }) {
  const item = items.find((i) => i.symbol === 'TCS' && i.exported_at) ?? items.find((i) => i.exported_at)
  return item ? <ExplainSection item={item} /> : null
}

function ExplainSection({ item }: { item: DemoItem }) {
  const navigate = useNavigate()
  const host = useRef<HTMLDivElement>(null)
  const inView = useInView(host, { once: true, margin: '-15% 0px' })
  const [a, setA] = useState<Analysis | null>(null)

  useEffect(() => { loadSnapshot(item.symbol).then(setA).catch(() => setA(null)) }, [item.symbol])

  return (
    <section className="home-section explain" id="explained" aria-labelledby="explain-title">
      <div className="section-copy">
        <h2 id="explain-title">Click any number. Watch how it was built.</h2>
        <p>
          Every figure in a report opens its own trace: which methods ran, how they were weighted,
          which rule decided. This is the real fair value for {a?.company_name ?? item.symbol}, replayed from the engine's output.
        </p>
        <Link className="text-link" to={`/s/${item.symbol}?explain=fairvalue`}>Open the full {item.symbol} report<ArrowUpRight size={16} /></Link>
      </div>
      <div ref={host}>
        <Window title={`${item.symbol} fair value, step by step`} className="explain-window">
          {a && inView ? (
            <div className="explain-body">
              <div className="explain-figure">
                <span className="label">Fair value (base)</span>
                <span className="value">{money(a.fair_value.base)}</span>
                <span className="detail">Range {money(a.fair_value.low)} to {money(a.fair_value.high)}</span>
              </div>
              <TraceBody trace={{ type: 'fairvalue' }} a={a} onJump={() => navigate(`/s/${item.symbol}?tab=valuation`)} />
            </div>
          ) : <div className="explain-body placeholder" aria-hidden="true" />}
        </Window>
      </div>
    </section>
  )
}

const EVIDENCE = [
  { figure: '36.0%', vs: 'vs 33.3% baseline', text: 'Balanced accuracy of our 40-day trend model in walk-forward tests. It misses our 5-point bar, so the dashboard hides it instead of showing a weak prediction.' },
  { figure: '86%', vs: '55% recall', text: 'Of the news events the local AI model reports, on 120 held-out headlines, are genuine company events. About half of real events are still missed, and the labels are not yet human-checked.' },
  { figure: '32', vs: 'stocks', text: 'The golden set re-checked after every engine change: routing, methods, allowed verdicts and sanity checks across sectors.' },
  { figure: '48', vs: 'NIFTY 50 companies', text: "Compared against analyst consensus. Consensus falls inside the engine's range for 52% of them, and the engine's relative calls are independent of analysts (rank correlation about 0)." },
]

export function HomePage() {
  const [items, setItems] = useState<DemoItem[]>(FALLBACK)
  const [sigma, setSigma] = useState(DEFAULT_SIGMA)
  const [preview, setPreview] = useState<{ item: DemoItem; vol: number } | null>(null)
  const [range, setRange] = useState<{ p10: number; p50: number; p90: number } | null>(null)
  const anchor = useRef<HTMLDivElement>(null)
  const hovered = useRef<string | null>(null)

  useEffect(() => {
    getManifest().then((m) => { if (m.items.length) setItems(m.items) })
  }, [])

  const onPreview = (item: DemoItem | null) => {
    hovered.current = item?.symbol ?? null
    if (!item || !item.exported_at) { setPreview(null); setSigma(DEFAULT_SIGMA); return }
    loadSnapshot(item.symbol).then((a) => {
      const vol = realisedVolatility(a)
      if (hovered.current !== item.symbol || vol == null) return
      setPreview({ item, vol })
      setSigma(Math.min(0.75, Math.max(0.12, vol)))
    }).catch(() => {})
  }

  const snapshotDay = items.find((i) => i.exported_at)?.exported_at

  // The simulation is always labelled where it is seen: beside the fan on
  // desktop, directly under it on phones (only one copy is ever displayed).
  const caption = (
    <>
      {preview
        ? <>Illustrative: {preview.item.symbol}'s realised volatility of <b>{Math.round(preview.vol * 100)}%</b> a year</>
        : <>Illustrative: ₹100 over 5 years at <b>{Math.round(DEFAULT_SIGMA * 100)}%</b> volatility</>}
      {range && <> spreads from <b>₹{Math.round(range.p10)}</b> to <b>₹{Math.round(range.p90)}</b> (10th to 90th percentile).</>}
      {' '}Not a forecast.
    </>
  )

  return (
    <StoryShell mainId="home-main">
        <section className="home-hero" aria-labelledby="home-title">
          <div className="hero-glow" aria-hidden="true"><span /><span /><span /></div>
          <FanCanvas originRef={anchor} sigma={sigma} onRange={setRange} />
          <div className="hero-content">
            <Rise><h1 id="home-title">Every stock has a thousand futures. We show you the range.</h1></Rise>
            <Rise delay={0.12}>
              <p className="hero-lead">
                Explainable analysis of Indian listed companies: fair-value ranges from several methods,
                an honest confidence score, and every number traceable to how it was reached.
              </p>
            </Rise>
            <Rise delay={0.22}>
              <div ref={anchor} className="fan-anchor"><SearchField id="hero-ticker" /></div>
              <p className="fan-caption narrow" aria-live="polite">{caption}</p>
            </Rise>
            <Rise delay={0.32}>
              <p className="picks-label">
                Showcase companies open instantly{snapshotDay ? ` (snapshots from ${snapshotDate(snapshotDay)})` : ''}.<span className="hover-hint"> Hover one to see its real volatility.</span>
              </p>
              <Picks items={items} onPreview={onPreview} />
            </Rise>
          </div>
          <p className="fan-caption wide" aria-live="polite">{caption}</p>
        </section>

        <ExplainDemo items={items} />

        <section className="home-section lab" id="lab" aria-labelledby="lab-title">
          <div className="section-copy wide">
            <h2 id="lab-title">Change the uncertainty. Watch the range move.</h2>
            <p>
              The same idea in three dimensions. Paths are ordered by where they end, so the cloud reads as a cone of possible
              futures. Scrub through time, raise volatility, drag to rotate.
            </p>
          </div>
          <Window title="Uncertainty lab: 220 simulated paths" className="lab-window">
            <Suspense fallback={<div className="stage-canvas" aria-hidden="true"><div className="stage-loading" /></div>}>
              <FuturesStage />
            </Suspense>
          </Window>
        </section>

        <section className="home-section evidence" id="evidence" aria-labelledby="evidence-title">
          <div className="section-copy">
            <h2 id="evidence-title">Checked, including what failed.</h2>
            <p>The validation behind the engine, in plain numbers. Each one is reproducible from a script in the repository.</p>
          </div>
          <Link className="text-link" to="/evidence">See every result, with charts<ArrowUpRight size={16} /></Link>
          <ol className="ledger">
            {EVIDENCE.map((e) => (
              <motion.li key={e.figure} initial={{ opacity: 0.001, y: 12 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-10% 0px' }} transition={{ duration: 0.7, ease: EASE }}>
                <span className="fig">{e.figure}<small>{e.vs}</small></span>
                <p>{e.text}</p>
              </motion.li>
            ))}
          </ol>
        </section>

        <section className="home-close" aria-labelledby="close-title">
          <h2 id="close-title">Pick a company and ask it why.</h2>
          <SearchField id="close-ticker" size="md" />
          <Picks items={items.slice(0, 6)} />
        </section>
    </StoryShell>
  )
}
