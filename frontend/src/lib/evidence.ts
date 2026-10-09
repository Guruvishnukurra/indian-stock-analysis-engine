// Validation evidence: the live /validation payload when the API is up,
// otherwise the copy exported by scripts/export_demo.py. Never invented.

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export interface ModelScores { balanced_accuracy: number; long_short_spread_40d: number | null }

export interface MlTrend {
  horizon_trading_days: number
  universe: string
  n_samples: number
  n_stocks: number
  per_year: { year: number; n_test: number; majority: number; momentum: number; technical: number; logistic: number; gradient_boosting: number }[]
  summary: Record<string, ModelScores>
  gate: { best_model: string; best_baseline: string; edge: number; required_edge: number; passed: boolean }
  caveats: string[]
}

export interface NewsScores {
  event_type_accuracy: number
  material_vs_noise_accuracy: number
  material_recall: number
  material_precision: number
  reported_items: number
  reported_exact_type_precision: number
}

export interface NewsEval {
  model: string
  split: string
  n_headlines: number
  human_checked: number
  llm: NewsScores
  llm_verified: NewsScores
  keyword_baseline: NewsScores
}

export interface ErrorRow { companies: number; median_abs_log_error: number; mean_abs_log_error: number }

export interface ConsensusRow { companies: number; median_engine_vs_consensus: number; median_abs_gap: number; consensus_inside_engine_range: number }

export interface Evidence {
  ml_trend: MlTrend | null
  peer_selection: Record<'PE' | 'PB', Record<string, ErrorRow>> | null
  news_events_test: NewsEval | null
  news_events_test2?: NewsEval | null
  consensus_comparison: {
    universe: string
    all: ConsensusRow
    high_confidence_only: ConsensusRow
    upside_rank_correlation: number
    by_company_type: Record<string, ConsensusRow>
    note?: string
  } | null
}

export interface GoldenRow {
  status: string
  company_type?: string
  stance?: string
  price?: number
  base?: number
  methods?: string[]
  confidence?: number
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${r.status}`)
  return r.json() as Promise<T>
}

export async function loadEvidence(): Promise<{ evidence: Evidence; source: 'live' | 'export' }> {
  try {
    return { evidence: await json<Evidence>(`${BASE}/validation`), source: 'live' }
  } catch {
    return { evidence: await json<Evidence>('/demo/validation.json'), source: 'export' }
  }
}

export function loadGolden(): Promise<Record<string, GoldenRow>> {
  return json<Record<string, GoldenRow>>('/demo/golden.json').catch(() => ({}))
}

// A median absolute log error of x means a typical miss of e^x - 1.
export const typicalMiss = (logError: number) => Math.exp(logError) - 1
