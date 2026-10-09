import { useEffect, useState } from 'react'
import { type Analysis, type HistoryRow, type Job, getHistory, startAnalysis, waitForJob } from './api'
import { findSnapshot, loadSnapshot } from './demo'

export type Source = { kind: 'snapshot'; exportedAt: string } | { kind: 'live' }

export interface AnalysisState {
  status: 'loading' | 'ready' | 'error'
  analysis: Analysis | null
  history: HistoryRow[]
  source: Source | null
  job: Job | null
  error: string | null
}

const START: AnalysisState = { status: 'loading', analysis: null, history: [], source: null, job: null, error: null }

/* Loads a report. Showcase tickers open from their snapshot instantly
   unless a live run is requested (live > 0, bumped by "Run live"). */
export function useAnalysis(ticker: string, includeNews: boolean, live: number): AnalysisState {
  const [state, setState] = useState<AnalysisState>(START)

  useEffect(() => {
    const controller = new AbortController()
    let current = true
    const update = (patch: Partial<AnalysisState>) => { if (current) setState((s) => ({ ...s, ...patch })) }

    async function load() {
      setState(START)
      try {
        const snapshot = live === 0 ? await findSnapshot(ticker) : undefined
        if (snapshot) {
          const analysis = await loadSnapshot(snapshot.symbol)
          update({ status: 'ready', analysis, source: { kind: 'snapshot', exportedAt: snapshot.exported_at } })
          getHistory(analysis.ticker).then((h) => update({ history: h.history })).catch(() => {})
          return
        }

        const started = await startAnalysis(ticker, includeNews, live > 0)
        update({ job: started })
        const finished = await waitForJob(
          started.job_id, (job) => update({ job }), controller.signal, started.status === 'done' ? 0 : 2000,
        )
        if (finished.status === 'failed' || !finished.result) throw new Error(finished.error ?? 'The analysis did not complete.')
        update({ status: 'ready', analysis: finished.result, source: { kind: 'live' } })
        getHistory(finished.ticker).then((h) => update({ history: h.history })).catch(() => {})
      } catch (e) {
        if ((e as Error).name !== 'AbortError') update({ status: 'error', error: (e as Error).message })
      }
    }

    load()
    return () => { current = false; controller.abort() }
    // includeNews only matters when a run starts; changing the switch must not restart a run
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, live])

  return state
}
