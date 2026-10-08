import { useEffect, useRef, useState } from 'react'
import { AnalysisView } from './components/AnalysisView'
import {
  type Analysis,
  type HistoryRow,
  type Job,
  getHistory,
  startAnalysis,
  waitForJob,
} from './lib/api'

const EXAMPLES = ['TCS', 'HDFCBANK', 'ATHERENERG', 'TATASTEEL', 'BAJFINANCE', 'WAAREEENER']

const DISCLAIMER =
  'Analytical assessment for research and education. Not investment advice, ' +
  'not a recommendation to buy or sell, and not a guaranteed prediction.'

type Theme = 'system' | 'light' | 'dark'

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

function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <rect x="6" y="13" width="20" height="6" rx="3" fill="#fff" opacity="0.35" />
      <rect x="15" y="7" width="2.5" height="18" rx="1.25" fill="#fff" />
    </svg>
  )
}

function EmptyState({ onPick }: { onPick: (t: string) => void }) {
  return (
    <section className="empty" aria-labelledby="empty-title">
      <div>
        <h1 id="empty-title">Analyse an Indian listed company</h1>
        <p className="section">
          Enter an NSE ticker to get a fair-value range, a confidence score and a plain-language
          verdict, with every number traceable to its method and period.
        </p>
        <div className="examples">
          {EXAMPLES.map((t) => (
            <button key={t} className="chip" onClick={() => onPick(t)}>{t}</button>
          ))}
        </div>
      </div>
      <ul className="plain" aria-label="What the analysis includes">
        <li><span className="mark neutral">1</span><span>Fair value from several methods, shown as a range, never a single number</span></li>
        <li><span className="mark neutral">2</span><span>What today's price assumes about growth or margins</span></li>
        <li><span className="mark neutral">3</span><span>Quality, valuation and timing judged separately</span></li>
        <li><span className="mark neutral">4</span><span>News sorted into real events and noise by a local AI model</span></li>
      </ul>
    </section>
  )
}

function LoadingState({ job, includeNews }: { job: Job | null; includeNews: boolean }) {
  const message =
    job?.status === 'running'
      ? `Fetching data and peers, then running the models${includeNews ? ', news tagging and the AI thesis' : ''}. First runs take ${includeNews ? '1 to 3 minutes' : 'about 30 seconds'}; repeats are faster.`
      : 'Queued.'
  return (
    <section aria-live="polite" aria-busy="true">
      <p className="progress-note"><span className="pulse" aria-hidden="true" />{message}</p>
      <div className="skeleton-line" style={{ width: '42%', height: 28 }} />
      <div className="skeleton-line section" style={{ width: '70%' }} />
      <div className="skeleton-line skeleton-block section" />
      <div className="grid two section">
        <div className="skeleton-line skeleton-block" style={{ height: 220 }} />
        <div className="skeleton-line skeleton-block" style={{ height: 220 }} />
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
  // The setting the RUNNING job was started with (the checkbox may change).
  const [runningWithNews, setRunningWithNews] = useState(true)
  const [theme, setTheme] = useTheme()
  const abort = useRef<AbortController | null>(null)

  async function run(symbol: string, force = false) {
    const clean = symbol.trim()
    if (!clean) {
      setError('Enter a ticker, for example TCS or HDFCBANK.')
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

  return (
    <div className="app">
      <a className="skip-link" href="#content">Skip to content</a>

      <header className="topbar">
        <a className="brand" href="/" onClick={(e) => { e.preventDefault(); setAnalysis(null); setError(null); window.history.replaceState(null, '', '/') }}>
          <BrandMark />
          <span>
            <strong>Stock Analysis Engine</strong>
            <small>NSE and BSE companies</small>
          </span>
        </a>

        <form className="search" onSubmit={(e) => { e.preventDefault(); run(ticker) }} role="search">
          <div className="field">
            <label htmlFor="ticker">Ticker</label>
            <input id="ticker" type="text" placeholder="TCS or TCS.NS" value={ticker}
              onChange={(e) => setTicker(e.target.value)} autoComplete="off" spellCheck={false}
              aria-invalid={error?.startsWith('Enter a ticker') ? true : undefined} />
          </div>
          <label className="toggle" htmlFor="include-news" title="Include news event tagging and the AI-written thesis (slower)">
            <input id="include-news" type="checkbox" checked={includeNews}
              onChange={(e) => setIncludeNews(e.target.checked)} aria-label="Include news and AI" />
            News and AI
          </label>
          <button className="btn primary" type="submit" disabled={busy}>{busy ? 'Analysing' : 'Analyse'}</button>
          {analysis && !busy && (
            <button className="btn" type="button" onClick={() => run(analysis.ticker, true)}
              title="Recompute instead of reusing a result from the last 6 hours">
              Refresh
            </button>
          )}
          <select className="btn select" value={theme} onChange={(e) => setTheme(e.target.value as Theme)} aria-label="Colour theme">
            <option value="system">Auto theme</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </form>
      </header>

      <main id="content" tabIndex={-1}>
        {error && !busy && (
          <section className="panel error-panel" role="alert">
            <p className="error">Could not analyse {ticker || 'that ticker'}.</p>
            <p className="secondary section">{error}</p>
            {!error.startsWith('Enter a ticker') && (
              <p className="muted small section">
                If this keeps happening, check the API is running:{' '}
                <code className="inline">.venv\Scripts\python.exe -m uvicorn src.api.main:app --port 8000</code>
              </p>
            )}
          </section>
        )}

        {!analysis && !busy && !error && <EmptyState onPick={(t) => run(t)} />}

        {busy && <LoadingState job={job} includeNews={runningWithNews} />}

        {analysis && !busy && <AnalysisView analysis={analysis} history={history} />}
      </main>

      <footer>
        <p className="disclaimer">{DISCLAIMER}</p>
      </footer>
    </div>
  )
}
