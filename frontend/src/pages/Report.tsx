import {
  ArrowClockwise,
  ChartLineUp,
  CircleHalf,
  ClockCounterClockwise,
  Lightning,
  MagnifyingGlass,
  Moon,
  Sun,
  WarningOctagon,
} from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { AnalysisView } from '../components/AnalysisView'
import type { Job } from '../lib/api'
import { bareSymbol, snapshotDate } from '../lib/demo'
import { type Theme, useTheme } from '../lib/theme'
import { type Source, useAnalysis } from '../lib/useAnalysis'

export const DISCLAIMER =
  'Analytical assessment for research and education. Not investment advice, ' +
  'not a recommendation to buy or sell, and not a guaranteed prediction.'

const THEMES: { id: Theme; label: string; Icon: typeof Sun }[] = [
  { id: 'light', label: 'Light theme', Icon: Sun },
  { id: 'dim', label: 'Dim theme (default)', Icon: CircleHalf },
  { id: 'dark', label: 'Dark theme', Icon: Moon },
]

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

function LoadingState({ job, includeNews, ticker }: { job: Job | null; includeNews: boolean; ticker: string }) {
  const message =
    job?.status === 'running'
      ? `Analysing ${ticker}: fetching data and peers, then running the models${includeNews ? ', news tagging and the AI thesis' : ''}. First runs take ${includeNews ? '1 to 3 minutes' : 'about 30 seconds'}; repeats are faster.`
      : `Preparing ${ticker}.`
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

function SourceBadge({ source, onLive }: { source: Source; onLive: () => void }) {
  if (source.kind === 'live') {
    return <p className="source-badge live"><Lightning size={14} weight="fill" aria-hidden="true" />Live analysis</p>
  }
  return (
    <p className="source-badge">
      <ClockCounterClockwise size={14} aria-hidden="true" />
      Snapshot from {snapshotDate(source.exportedAt)}
      <button type="button" className="link-btn" onClick={onLive}>Run live now</button>
    </p>
  )
}

// Keyed by ticker so each company starts with fresh page state.
export function ReportPage() {
  const { ticker = '' } = useParams()
  return <Report key={bareSymbol(ticker)} param={ticker} />
}

function Report({ param }: { param: string }) {
  const navigate = useNavigate()
  const symbol = bareSymbol(param)
  const [query, setQuery] = useState(symbol)
  const [includeNews, setIncludeNews] = useState(true)
  const [live, setLive] = useState(0)
  const [theme, setTheme] = useTheme()
  const input = useRef<HTMLInputElement>(null)
  const state = useAnalysis(symbol, includeNews, live)

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

  const submit = () => {
    const clean = bareSymbol(query)
    if (!clean) { input.current?.focus(); return }
    if (clean === symbol) setLive((n) => n + 1)
    else navigate(`/s/${clean}`)
  }

  const busy = state.status === 'loading'

  return (
    <>
      <a className="skip-link" href="#content">Skip to content</a>

      <header className="appbar">
        <div className="appbar-inner">
          <Link className="brand" to="/">
            <span className="brand-mark" aria-hidden="true"><ChartLineUp size={18} weight="bold" /></span>
            <span className="brand-name">Stock Analysis Engine</span>
          </Link>

          <form className="searchbar" role="search" onSubmit={(e) => { e.preventDefault(); submit() }}>
            <MagnifyingGlass className="lead" size={18} aria-hidden="true" />
            <label htmlFor="ticker" className="visually-hidden">NSE ticker</label>
            <input id="ticker" ref={input} type="text" placeholder="Ticker, e.g. TCS"
              value={query} onChange={(e) => setQuery(e.target.value)} autoComplete="off" spellCheck={false} />
            {!query && <kbd aria-hidden="true">/</kbd>}
            <button className="btn btn-primary" type="submit" disabled={busy} style={{ height: 32 }}>
              {busy ? 'Analysing' : 'Analyse'}
            </button>
          </form>

          <div className="bar-actions">
            <button type="button" className="switch" role="switch" aria-checked={includeNews}
              onClick={() => setIncludeNews((v) => !v)}
              title="Include news event tagging and the AI-written thesis in live runs (slower)">
              <span className="track" aria-hidden="true"><span className="thumb" /></span>
              <span className="label-text">News and AI</span>
              <span className="visually-hidden">Include news and AI</span>
            </button>
            {state.status === 'ready' && (
              <button className="btn btn-ghost btn-icon" type="button" onClick={() => setLive((n) => n + 1)}
                aria-label="Recompute this analysis live" title="Recompute with the live engine">
                <ArrowClockwise size={18} />
              </button>
            )}
            <ThemeControl theme={theme} onChange={setTheme} />
          </div>
        </div>
      </header>

      <div className="shell">
        <main id="content" tabIndex={-1}>
          {state.status === 'error' && (
            <section className="card error-card" role="alert">
              <span className="ic" aria-hidden="true"><WarningOctagon size={20} weight="bold" /></span>
              <div className="stack">
                <h2>Could not analyse {symbol}</h2>
                <p className="secondary">{state.error}</p>
                <p className="muted small">
                  If this keeps happening, check the API is running:{' '}
                  <code className="inline">.venv\Scripts\python.exe -m uvicorn src.api.main:app --port 8000</code>
                </p>
              </div>
            </section>
          )}

          {busy && <LoadingState job={state.job} includeNews={includeNews} ticker={symbol} />}

          {state.status === 'ready' && state.analysis && (
            <>
              {state.source && <SourceBadge source={state.source} onLive={() => setLive((n) => n + 1)} />}
              <AnalysisView analysis={state.analysis} history={state.history} />
            </>
          )}
        </main>

        <footer className="site">
          <p>{DISCLAIMER}</p>
        </footer>
      </div>
    </>
  )
}
