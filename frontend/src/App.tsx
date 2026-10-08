import {
  ArrowClockwise,
  ArrowRight,
  ChartLineUp,
  CheckCircle,
  Desktop,
  MagnifyingGlass,
  Moon,
  Sun,
  WarningOctagon,
} from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { AnalysisView } from './components/AnalysisView'
import { Backdrop3D } from './components/Backdrop3D'
import {
  type Analysis,
  type HistoryRow,
  type Job,
  getHistory,
  startAnalysis,
  waitForJob,
} from './lib/api'

const EXAMPLES: [string, string][] = [
  ['TCS', 'IT services, steady compounder'],
  ['HDFCBANK', 'Private bank'],
  ['ATHERENERG', 'Loss-making EV maker'],
  ['TATASTEEL', 'Cyclical metals'],
  ['BAJFINANCE', 'Consumer lender (NBFC)'],
  ['WAAREEENER', 'Capex-heavy solar'],
]

const DISCLAIMER =
  'Analytical assessment for research and education. Not investment advice, ' +
  'not a recommendation to buy or sell, and not a guaranteed prediction.'

type Theme = 'system' | 'light' | 'dark'

const THEMES: { id: Theme; label: string; Icon: typeof Sun }[] = [
  { id: 'light', label: 'Light theme', Icon: Sun },
  { id: 'dark', label: 'Dark theme', Icon: Moon },
  { id: 'system', label: 'Match system theme', Icon: Desktop },
]

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem('theme') as Theme) || 'system'
    } catch {
      return 'system'
    }
  })

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* storage unavailable: theme still applies for this visit */
    }
  }, [theme])

  return [theme, setTheme]
}

function ThemeControl({ theme, onChange }: { theme: Theme; onChange: (t: Theme) => void }) {
  return (
    <div className="segmented" role="radiogroup" aria-label="Colour theme">
      {THEMES.map(({ id, label, Icon }) => (
        <button key={id} type="button" role="radio" aria-checked={theme === id} aria-label={label}
          title={label} onClick={() => onChange(id)}>
          <Icon size={16} weight={theme === id ? 'fill' : 'regular'} />
        </button>
      ))}
    </div>
  )
}

function Welcome({ onPick }: { onPick: (t: string) => void }) {
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div>
        <h1 id="welcome-title">Understand what a stock is worth, and why.</h1>
        <p className="lead">
          Enter an NSE ticker for a fair-value range, a confidence score and a plain-language
          verdict. Every number is traceable to its method and period.
        </p>
        <ul className="list points" aria-label="What the analysis includes">
          {[
            'Fair value from several methods, shown as a range',
            "What today's price assumes about growth and margins",
            'Quality, valuation and timing judged separately',
            'News sorted into real events and noise by a local AI model',
          ].map((p) => (
            <li key={p}><span className="ic up" aria-hidden="true"><CheckCircle size={14} weight="bold" /></span><span>{p}</span></li>
          ))}
        </ul>
      </div>
      <div>
        <Backdrop3D />
        <p className="muted small" style={{ marginBottom: 10 }}>Try one of these</p>
        <div className="pick-grid">
          {EXAMPLES.map(([t, d]) => (
            <button key={t} type="button" className="pick" onClick={() => onPick(t)}>
              <span className="t">{t}<ArrowRight size={14} aria-hidden="true" /></span>
              <span className="d">{d}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

function LoadingState({ job, includeNews, ticker }: { job: Job | null; includeNews: boolean; ticker: string }) {
  const message =
    job?.status === 'running'
      ? `Analysing ${ticker}: fetching data and peers, then running the models${includeNews ? ', news tagging and the AI thesis' : ''}. First runs take ${includeNews ? '1 to 3 minutes' : 'about 30 seconds'}; repeats are faster.`
      : `Queued ${ticker}.`
  return (
    <section aria-live="polite" aria-busy="true">
      <p className="loading-head"><span className="pulse" aria-hidden="true" />{message}</p>
      <div className="stack" aria-hidden="true" style={{ marginTop: 18 }}>
        <div className="sk" style={{ width: '38%', height: 34 }} />
        <div className="sk" style={{ width: '22%', height: 18 }} />
        <div className="kpis" style={{ marginTop: 8 }}>
          {Array.from({ length: 5 }, (_, i) => <div key={i} className="sk" style={{ height: 92 }} />)}
        </div>
        <div className="sk" style={{ height: 44, marginTop: 8 }} />
        <div className="sk" style={{ height: 120 }} />
        <div className="grid cols-2">
          <div className="sk" style={{ height: 220 }} />
          <div className="sk" style={{ height: 220 }} />
        </div>
      </div>
    </section>
  )
}

export default function App() {
  const [ticker, setTicker] = useState(() => new URLSearchParams(location.search).get('t') ?? '')
  const [includeNews, setIncludeNews] = useState(true)
  const [job, setJob] = useState<Job | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [history, setHistory] = useState<HistoryRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // The setting the RUNNING job was started with (the switch may change).
  const [runningWithNews, setRunningWithNews] = useState(true)
  const [theme, setTheme] = useTheme()
  const abort = useRef<AbortController | null>(null)
  const input = useRef<HTMLInputElement>(null)

  async function run(symbol: string, force = false) {
    const clean = symbol.trim()
    if (!clean) {
      setError('Enter a ticker, for example TCS or HDFCBANK.')
      input.current?.focus()
      return
    }

    abort.current?.abort()
    const controller = new AbortController()
    abort.current = controller

    setBusy(true)
    setRunningWithNews(includeNews)
    setError(null)
    setJob(null)
    setTicker(clean.toUpperCase())

    try {
      const started = await startAnalysis(clean, includeNews, force)
      setJob(started)

      const finished = await waitForJob(
        started.job_id, setJob, controller.signal, started.status === 'done' ? 0 : 2000,
      )

      if (finished.status === 'failed' || !finished.result) {
        throw new Error(finished.error ?? 'The analysis did not complete.')
      }

      setAnalysis(finished.result)
      setHistory([])
      getHistory(finished.ticker).then((h) => setHistory(h.history)).catch(() => setHistory([]))

      const url = new URL(location.href)
      url.searchParams.set('t', finished.ticker)
      window.history.replaceState(null, '', url)
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message)
    } finally {
      if (abort.current === controller) setBusy(false)
    }
  }

  // Deep link: ?t=TCS.NS opens that analysis directly.
  useEffect(() => {
    if (ticker) run(ticker)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // "/" focuses the search box from anywhere on the page.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) {
        e.preventDefault()
        input.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const goHome = () => {
    abort.current?.abort()
    setBusy(false)
    setAnalysis(null)
    setError(null)
    setTicker('')
    window.history.replaceState(null, '', '/')
  }

  return (
    <>
      <a className="skip-link" href="#content">Skip to content</a>

      <header className="appbar">
        <div className="appbar-inner">
          <a className="brand" href="/" onClick={(e) => { e.preventDefault(); goHome() }}>
            <span className="brand-mark" aria-hidden="true"><ChartLineUp size={18} weight="bold" /></span>
            <span className="brand-name">Stock Analysis Engine</span>
          </a>

          <form className="searchbar" role="search" onSubmit={(e) => { e.preventDefault(); run(ticker) }}>
            <MagnifyingGlass className="lead" size={18} aria-hidden="true" />
            <label htmlFor="ticker" className="visually-hidden">NSE ticker</label>
            <input id="ticker" ref={input} type="text" placeholder="Ticker, e.g. TCS"
              value={ticker} onChange={(e) => setTicker(e.target.value)} autoComplete="off" spellCheck={false}
              aria-invalid={error?.startsWith('Enter a ticker') ? true : undefined} />
            {!ticker && <kbd aria-hidden="true">/</kbd>}
            <button className="btn btn-primary" type="submit" disabled={busy} style={{ height: 32 }}>
              {busy ? 'Analysing' : 'Analyse'}
            </button>
          </form>

          <div className="bar-actions">
            <button type="button" className="switch" role="switch" aria-checked={includeNews}
              onClick={() => setIncludeNews((v) => !v)}
              title="Include news event tagging and the AI-written thesis (slower)">
              <span className="track" aria-hidden="true"><span className="thumb" /></span>
              <span className="label-text">News and AI</span>
              <span className="visually-hidden">Include news and AI</span>
            </button>
            {analysis && !busy && (
              <button className="btn btn-ghost btn-icon" type="button" onClick={() => run(analysis.ticker, true)}
                aria-label="Recompute this analysis" title="Recompute instead of reusing a result from the last 6 hours">
                <ArrowClockwise size={18} />
              </button>
            )}
            <ThemeControl theme={theme} onChange={setTheme} />
          </div>
        </div>
      </header>

      <div className="shell">
        <main id="content" tabIndex={-1}>
          {error && !busy && (
            <section className="card error-card" role="alert">
              <span className="ic" aria-hidden="true"><WarningOctagon size={20} weight="bold" /></span>
              <div className="stack">
                <h2>Could not analyse {ticker || 'that ticker'}</h2>
                <p className="secondary">{error}</p>
                {!error.startsWith('Enter a ticker') && (
                  <p className="muted small">
                    If this keeps happening, check the API is running:{' '}
                    <code className="inline">.venv\Scripts\python.exe -m uvicorn src.api.main:app --port 8000</code>
                  </p>
                )}
              </div>
            </section>
          )}

          {!analysis && !busy && <Welcome onPick={(t) => run(t)} />}

          {busy && <LoadingState job={job} includeNews={runningWithNews} ticker={ticker} />}

          {analysis && !busy && <AnalysisView analysis={analysis} history={history} />}
        </main>

        <footer className="site">
          <p>{DISCLAIMER}</p>
        </footer>
      </div>
    </>
  )
}
