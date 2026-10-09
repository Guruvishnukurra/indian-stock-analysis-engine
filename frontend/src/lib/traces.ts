import type { Analysis } from './api'

// Shared definitions for the "how we got here" traces (components/Traces.tsx).

export type Trace =
  | { type: 'stance' | 'fairvalue' | 'upside' | 'confidence' | 'quality' | 'timing' }
  | { type: 'method'; key: string }
  | { type: 'metric'; key: string }

export type TabTarget = 'overview' | 'valuation' | 'fundamentals' | 'market' | 'news'

export const METHOD_INFO: Record<string, { name: string; what: string }> = {
  dcf: { name: 'Discounted cash flow', what: "Projects free cash flow for ten years, adds a terminal value, and discounts everything back at the company's cost of capital. It values the business on its own cash generation, independent of what the market pays for peers." },
  growth_dcf: { name: 'Growth-stage DCF', what: 'For companies without usable earnings: simulates thousands of paths for revenue growth and the margin the business might eventually reach, then discounts the resulting cash flows. It answers "what future does the price need?" rather than giving a precise value.' },
  peer_pe: { name: 'Peer P/E', what: "Applies the price-to-earnings multiple that comparable Indian listed companies trade at to this company's earnings per share. The interquartile range of peer multiples gives the low and high values." },
  peer_pb: { name: 'Peer P/B', what: 'Applies peer price-to-book multiples to book value per share. Used mainly for banks and lenders, whose assets are mostly financial and marked close to book.' },
  peer_evs: { name: 'Peer EV/Sales', what: 'Applies peer enterprise-value-to-sales multiples. Used when earnings are not meaningful yet, then adjusts for net cash or debt to get a per-share value.' },
  historical_pe: { name: 'Historical P/E', what: "Applies the stock's own typical P/E over recent years to current earnings. Shown as context only: it tells you whether the stock is cheap versus its own history, not versus fundamentals." },
}

export const METRIC_INFO: Record<string, string> = {
  revenue_growth: 'How fast sales grew over the last year. Sustained growth funds future profits; one-off jumps from acquisitions or price spikes are less reliable.',
  profit_growth: 'Growth in net profit over the last year. Faster than revenue growth means margins are expanding.',
  eps_growth: 'Growth in earnings per share. Unlike profit growth, it accounts for new shares issued, so it shows what each existing shareholder actually gained.',
  operating_margin: 'The share of revenue left after operating costs. A high, stable margin points to pricing power or cost advantages.',
  roe: "Profit earned per rupee of shareholders' equity. High ROE with low debt is a classic sign of a quality business.",
  debt_to_equity: 'Borrowings relative to equity. More debt means fixed obligations that bite in a downturn. Lenders are judged on different leverage norms.',
  fcf_conversion: 'Free cash flow divided by net income. Below 1 means part of reported profit is tied up in working capital or capex rather than arriving as cash.',
}

export function traceHeading(t: Trace, a: Analysis): { title: string; eyebrow: string; tab: TabTarget } {
  switch (t.type) {
    case 'stance': return { title: 'How the stance was decided', eyebrow: 'Overall', tab: 'overview' }
    case 'fairvalue': return { title: 'How the fair value was built', eyebrow: 'Fair value', tab: 'valuation' }
    case 'upside': return { title: 'From fair value to upside', eyebrow: 'Upside', tab: 'valuation' }
    case 'confidence': return { title: 'Why this confidence score', eyebrow: 'Confidence', tab: 'news' }
    case 'quality': return { title: 'How quality was scored', eyebrow: 'Quality', tab: 'fundamentals' }
    case 'timing': return { title: 'How timing was read', eyebrow: 'Timing', tab: 'market' }
    case 'method': return { title: METHOD_INFO[t.key]?.name ?? humanKey(t.key), eyebrow: 'Valuation method', tab: 'valuation' }
    case 'metric': return { title: a.fundamental_score.metrics.find((m) => m.key === t.key)?.label ?? humanKey(t.key), eyebrow: 'Fundamental metric', tab: 'fundamentals' }
  }
}

export function humanKey(key: string) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bWacc\b/, 'WACC').replace(/\bFcf\b/, 'FCF').replace(/\bEps\b/, 'EPS')
}
