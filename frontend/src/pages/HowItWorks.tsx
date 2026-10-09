import { ArrowUpRight } from '@phosphor-icons/react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ConfidenceScene, DataScene, RouteScene, ValueScene, VerdictScene } from '../components/story/Scenes'
import { StoryShell } from '../components/story/StoryShell'
import { SlideIndicator } from '../motion/SlideIndicator'
import type { Analysis } from '../lib/api'
import { loadSnapshot } from '../lib/demo'
import { crore, money, pct, title } from '../lib/format'

const COMPANIES = [
  { symbol: 'TCS', note: 'IT services' },
  { symbol: 'HDFCBANK', note: 'Bank' },
  { symbol: 'ATHERENERG', note: 'Loss-making' },
]

interface StepDef {
  id: string
  short: string
  heading: string
  body: string
  fact: (a: Analysis) => string
  scene: (a: Analysis) => ReactNode
  sceneKey: string
}

const methodCount = (a: Analysis) => Object.keys(a.fair_value.weights_used ?? {}).length

const STEPS: StepDef[] = [
  {
    id: 'data', short: 'Filings', sceneKey: 'data',
    heading: 'It starts with the filings.',
    body: 'Four years of annual statements and a year of daily prices. Every figure keeps the period it came from, and figures from different periods are never mixed in one ratio. One-off gains and charges are stripped from earnings when the source reports them.',
    fact: (a) => {
      const last = (a.fundamentals_annual ?? []).at(-1)
      return last ? `${a.company_name}: revenue ${crore(last.Revenue as number)}, net income ${crore(last.Net_Income as number)} in the latest year.` : a.company_name
    },
    scene: (a) => <DataScene a={a} />,
  },
  {
    id: 'route', short: 'Routing', sceneKey: 'route',
    heading: 'First: what kind of business is this?',
    body: 'Banks, lenders, cyclicals, capex-heavy and loss-making companies need different tools. The engine classifies the company, switches on only the methods that fit, and records why every other method was ruled out.',
    fact: (a) => `Analysed as ${title(a.company_profile.company_type).toLowerCase()}: ${methodCount(a)} core method${methodCount(a) === 1 ? '' : 's'} apply.`,
    scene: (a) => <RouteScene a={a} />,
  },
  {
    id: 'methods', short: 'Methods', sceneKey: 'value',
    heading: 'Each method values the company on its own.',
    body: "A DCF discounts the company's own cash flows; peer methods borrow what comparable Indian companies trade at. Each method gives a low, a base and a high value, drawn here against today's price.",
    fact: (a) => `Today's price: ${money(a.current_price)}.`,
    scene: (a) => <ValueScene a={a} stage="methods" />,
  },
  {
    id: 'blend', short: 'Blend', sceneKey: 'value',
    heading: 'Then they are blended by weight.',
    body: "Core methods are weighted by how well they suit this type of company and how much they agree. Context methods, such as the stock's own historical P/E, are shown but never move the result.",
    fact: (a) => `Blended base value: ${money(a.fair_value.base)}.`,
    scene: (a) => <ValueScene a={a} stage="blend" />,
  },
  {
    id: 'range', short: 'Range', sceneKey: 'value',
    heading: 'The answer is a range, not a target.',
    body: "The range spans every core method's estimate and widens when the methods disagree. Upside is measured from today's price to the base of that range, never to the optimistic end.",
    fact: (a) => `${money(a.fair_value.low)} to ${money(a.fair_value.high)}, base ${pct(a.fair_value.upside_base, true, 0)} from the price.`,
    scene: (a) => <ValueScene a={a} stage="range" />,
  },
  {
    id: 'confidence', short: 'Confidence', sceneKey: 'confidence',
    heading: 'How far should you trust it?',
    body: 'Confidence scores the evidence, not the stock: how complete the data is, how many independent methods apply, whether they agree, how good the peer set is, and how stable earnings have been.',
    fact: (a) => `Confidence ${a.confidence.score}/100 (${a.confidence.label.toLowerCase()}).`,
    scene: (a) => <ConfidenceScene a={a} />,
  },
  {
    id: 'verdict', short: 'Verdict', sceneKey: 'verdict',
    heading: 'Only then, a verdict.',
    body: 'Quality, valuation and timing are judged separately. Safety gates come first: a loss-making company, or one the methods cannot fit, gets NOT RATED instead of a guess. Every rule is in the code, and every report can replay it.',
    fact: (a) => { const s = a.explanation.stance.toLowerCase(); return `Stance: ${s[0].toUpperCase()}${s.slice(1)}.` },
    scene: (a) => <VerdictScene a={a} />,
  },
]

function CompanySwitch({ value, onChange }: { value: string; onChange: (s: string) => void }) {
  const index = Math.max(0, COMPANIES.findIndex((c) => c.symbol === value))
  return (
    <div className="seg story-seg" role="radiogroup" aria-label="Company to follow">
      <SlideIndicator index={index} className="seg-pill" kind="pill" />
      {COMPANIES.map((c) => (
        <button key={c.symbol} type="button" role="radio" aria-checked={value === c.symbol} onClick={() => onChange(c.symbol)}>
          {c.symbol}<span className="seg-note">{c.note}</span>
        </button>
      ))}
    </div>
  )
}

export function HowItWorksPage() {
  const [params, setParams] = useSearchParams()
  const symbol = COMPANIES.some((c) => c.symbol === params.get('c')) ? params.get('c')! : 'TCS'
  const [data, setData] = useState<{ symbol: string; a: Analysis } | null>(null)
  const [active, setActive] = useState(0)
  const steps = useRef<(HTMLElement | null)[]>([])
  const reduce = useReducedMotion()
  const a = data?.a ?? null

  useEffect(() => {
    let current = true
    loadSnapshot(symbol).then((loaded) => { if (current) setData({ symbol, a: loaded }) }).catch(() => {})
    return () => { current = false }
  }, [symbol])

  // The step whose text crosses the middle of the viewport drives the window.
  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.index))
    }, { rootMargin: '-45% 0px -50% 0px' })
    steps.current.forEach((el) => el && io.observe(el))
    return () => io.disconnect()
  }, [a])

  const step = STEPS[active]

  return (
    <StoryShell mainId="how-main">
      <header className="page-head">
        <h1>How the engine reaches a verdict</h1>
        <p className="page-lead">
          Seven steps from raw filings to a stance, followed with one real company. Switch companies to see the
          route change: a bank and a loss-making business are valued with different tools.
        </p>
        <CompanySwitch value={symbol} onChange={(s) => setParams({ c: s }, { replace: true })} />
      </header>

      {!a ? (
        <div className="story-loading" aria-busy="true">Loading {symbol}'s snapshot</div>
      ) : (
        <div className="story-grid">
          <div className="story-sticky" aria-hidden="true">
            <div className="window scope-dark story-window">
              <div className="window-bar story-bar">
                <span className="window-title">{a.company_name}</span>
                <ol className="story-progress">
                  {STEPS.map((s, i) => (
                    <li key={s.id} className={i === active ? 'on' : i < active ? 'done' : ''}><span>{s.short}</span></li>
                  ))}
                </ol>
              </div>
              <div className="story-stage">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div key={`${symbol}-${step.sceneKey}`} className="story-scene"
                    initial={reduce ? false : { opacity: 0, y: 14, filter: 'blur(6px)' }}
                    animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                    exit={reduce ? undefined : { opacity: 0, y: -10, filter: 'blur(6px)' }}
                    transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
                    {step.scene(a)}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>

          <ol className="story-steps">
            {STEPS.map((s, i) => (
              <li key={s.id} ref={(el) => { steps.current[i] = el }} data-index={i} className={i === active ? 'on' : ''}>
                <span className="step-count">{i + 1} of {STEPS.length}</span>
                <h2>{s.heading}</h2>
                <p>{s.body}</p>
                <p className="step-fact">{s.fact(a)}</p>
                <div className="window scope-dark inline-scene">{s.scene(a)}</div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {a && (
        <section className="story-end">
          <h2>Every report replays these steps for its own numbers.</h2>
          <div className="story-links">
            <Link className="text-link" to={`/s/${symbol}?explain=fairvalue`}>Open {symbol}'s fair-value trace<ArrowUpRight size={16} /></Link>
            <Link className="text-link" to="/evidence">See how the engine was validated<ArrowUpRight size={16} /></Link>
          </div>
        </section>
      )}
    </StoryShell>
  )
}
