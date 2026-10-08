// Formatting helpers. Every helper tolerates missing values, because the
// engine reports "unavailable" rather than inventing numbers.

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function money(value: number | null | undefined): string {
  if (!isNum(value)) return 'n/a'
  if (value <= 0) return '₹0'
  const digits = value >= 100 ? 0 : 2
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: 0 })}`
}

export function pct(value: number | null | undefined, signed = true, digits = 1): string {
  if (!isNum(value)) return 'n/a'
  const sign = signed && value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

export function pp(value: number | null | undefined): string {
  if (!isNum(value)) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)} pp`
}

export function num(value: number | null | undefined, digits = 2): string {
  return isNum(value) ? value.toFixed(digits) : 'n/a'
}

export function crore(value: number | null | undefined): string {
  if (!isNum(value)) return 'n/a'
  return `₹${(value / 1e7).toLocaleString('en-IN', { maximumFractionDigits: 0 })} cr`
}

export function metricValue(value: number, unit: string): string {
  return unit === '%' ? `${value.toFixed(1)}%` : `${value.toFixed(2)}x`
}

export function title(text: string): string {
  return text.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function dateLabel(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export { isNum }

export function assessmentTone(label: string): 'good' | 'warn' | 'bad' {
  return label === 'Strong' ? 'good' : label === 'Moderate' ? 'warn' : 'bad'
}
