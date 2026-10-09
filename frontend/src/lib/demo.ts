import type { Analysis } from './api'

// Demo mode: showcase analyses exported by scripts/export_demo.py live in
// public/demo and open instantly. They are always labelled as snapshots.

export interface DemoItem {
  symbol: string
  ticker: string
  name?: string
  description?: string
  stance?: string
  price?: number
  exported_at: string
}

interface Manifest { engine_version?: string; items: DemoItem[] }

let manifest: Promise<Manifest> | null = null
const snapshots = new Map<string, Promise<Analysis>>()

export function bareSymbol(ticker: string) {
  return ticker.trim().toUpperCase().replace(/\.(NS|BO)$/, '')
}

export function getManifest(): Promise<Manifest> {
  manifest ??= fetch('/demo/manifest.json')
    .then((r) => (r.ok ? (r.json() as Promise<Manifest>) : { items: [] }))
    .catch(() => ({ items: [] }))
  return manifest
}

export async function findSnapshot(ticker: string): Promise<DemoItem | undefined> {
  const { items } = await getManifest()
  return items.find((i) => i.symbol === bareSymbol(ticker))
}

export function loadSnapshot(symbol: string): Promise<Analysis> {
  const key = bareSymbol(symbol)
  let pending = snapshots.get(key)
  if (!pending) {
    pending = fetch(`/demo/${key}.json`).then((r) => {
      if (!r.ok) throw new Error(`Snapshot for ${key} is missing.`)
      return r.json() as Promise<Analysis>
    })
    pending.catch(() => snapshots.delete(key))
    snapshots.set(key, pending)
  }
  return pending
}

// Annualised volatility of daily log returns over the stored price history.
export function realisedVolatility(a: Analysis): number | null {
  const closes = a.price_history.map((r) => r.Close).filter((v): v is number => v != null && v > 0)
  if (closes.length < 30) return null
  const returns = closes.slice(1).map((c, i) => Math.log(c / closes[i]))
  const mean = returns.reduce((s, r) => s + r, 0) / returns.length
  const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1)
  return Math.sqrt(variance * 252)
}

export function snapshotDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
