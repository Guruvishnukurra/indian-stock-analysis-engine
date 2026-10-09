// Thin client for the FastAPI backend (see src/api/main.py).
// Types describe only the fields the dashboard uses; every field the
// engine may omit is optional, because missing data is normal.

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export type Stance = 'ATTRACTIVE' | 'WATCH' | 'AVOID' | 'NOT RATED' | 'INSUFFICIENT DATA'

export interface MethodResult {
  available: boolean
  reason?: string
  base?: number
  low?: number
  high?: number
  range_basis?: string
  peer_count?: number
  terminal_share?: number | null
  sensitivity?: Record<string, Record<string, number | null>>
  assumptions?: Record<string, unknown>
  simulation?: { runs: number; p10: number; p50: number; p90: number; share_justifying_price: number }
  funding?: {
    peak_cash_burn: number
    net_cash: number
    first_positive_fcf_year: number | null
    funding_gap: number
    gap_share_of_market_cap: number | null
  }
  cases?: Record<string, { start_growth: number; target_margin: number; value: number }>
  implied_margin?: number | null
  multiple_median?: number
  multiple_low?: number
  multiple_high?: number
}

export interface FairValue {
  available: boolean
  reason?: string
  base?: number
  low?: number
  high?: number
  upside_base?: number
  upside_low?: number
  upside_high?: number
  methods_used: string[]
  weights_used?: Record<string, number>
  method_upsides?: Record<string, number>
  context_methods?: Record<string, { base: number; upside: number }>
  dispersion?: { coefficient_of_variation: number | null; max_to_min?: number } | null
  widened_for_disagreement?: boolean
}

export interface MetricItem {
  key: string
  label: string
  value: number
  unit: string
  score: number
  assessment: 'Strong' | 'Moderate' | 'Weak'
  source?: string
}

export interface Verdicts {
  quality: string
  valuation: { label: string; log_gap: number | null; fair_value_to_price?: number; measure?: string }
  timing: { label: string; horizon: string; notes: string[] }
  triggers: string[]
}

export interface Analysis {
  ticker: string
  status: string
  company_name: string
  sector?: string
  industry?: string
  current_price: number
  conclusion?: string | null
  inputs: {
    consensus_target?: number | null
    analyst_count?: number | null
    risk_premium_reasons?: string[]
  }
  company_profile: {
    company_type: string; classification_certainty?: string; valuation_family?: string
    earnings_usable?: boolean; holding_company?: boolean
  }
  fair_value: FairValue
  method_results: Record<string, MethodResult>
  valuation_selection?: { selected_methods: string[]; excluded_methods: Record<string, string> }
  confidence: {
    score: number; label: string; reasons: string[]; concerns: string[]
    components?: { name: string; points: number; max: number; positives: string[]; concerns: string[] }[]
  }
  growth_confidence?: { level: string; reasons: string[] } | null
  fundamental_score: { score: number | null; label: string; metrics: MetricItem[]; missing: string[] }
  technical_score: { score: number | null; label: string; signals: [number, string][] }
  market_score: { score: number | null; label: string }
  market_context: {
    stock_return?: number | null
    market_return?: number | null
    sector_return?: number | null
    relative_to_market?: number | null
    relative_to_sector?: number | null
  }
  sector_benchmark?: { name: string }
  beta?: number | null
  latest_technical?: { RSI_14?: number | null }
  price_history: { date: string; Close: number | null; SMA_50: number | null; SMA_200: number | null }[]
  expectations?: { available: boolean; method?: string; assessment?: string; summary?: string; reason?: string }
  scenarios?: {
    available: boolean
    reason?: string
    horizon_years?: number
    cases?: Record<string, { growth: number; exit_pe: number; value: number; upside: number }>
    payoff_summary?: string
  }
  news: {
    label?: string
    news_score?: number | null
    sentiment_basis?: string
    raw_article_count?: number
    duplicates_removed?: number
    events?: {
      catalysts: string[]
      risks: string[]
      other_material?: string[]
      material_share?: number | null
      noise_share?: number | null
      accuracy_note?: string
    } | null
  }
  ml_trend: { available: boolean; reason?: string; validation?: { edge: number; required_edge: number } }
  thesis?: { available: boolean; text?: string; note?: string }
  explanation: {
    stance: Stance
    verdicts?: Verdicts
    why_bullish: string[]
    why_not_bullish: string[]
    risks: string[]
    data_limitations: string[]
    interpretation: string
  }
}

export interface Job {
  job_id: string
  ticker: string
  status: 'queued' | 'running' | 'done' | 'failed'
  error?: string | null
  created_at?: string
  result?: Analysis
  disclaimer?: string
}

export interface HistoryRow {
  job_id: string
  created_at: string
  price?: number
  stance?: Stance
  fair_value_low?: number
  fair_value_base?: number
  fair_value_high?: number
  confidence?: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

export function startAnalysis(ticker: string, includeNews: boolean, force = false) {
  return request<Job & { reused: boolean }>('/analyses', {
    method: 'POST',
    body: JSON.stringify({ ticker, include_news: includeNews, force }),
  })
}

export function getJob(jobId: string) {
  return request<Job>(`/analyses/${encodeURIComponent(jobId)}`)
}

export function getHistory(ticker: string) {
  return request<{ ticker: string; history: HistoryRow[] }>(
    `/stocks/${encodeURIComponent(ticker)}/history`,
  )
}

export function getHealth() {
  return request<{ status: string; local_llm: { model: string; available: boolean }; gpu: boolean }>('/health')
}

// Polls a job until it finishes. Calls onUpdate on every status change.
export async function waitForJob(
  jobId: string,
  onUpdate: (job: Job) => void,
  signal: AbortSignal,
  intervalMs = 2000,
): Promise<Job> {
  for (;;) {
    if (signal.aborted) throw new DOMException('Cancelled', 'AbortError')
    const job = await getJob(jobId)
    onUpdate(job)
    if (job.status === 'done' || job.status === 'failed') return job
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
}
