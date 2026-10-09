import { useState } from 'react'
import { money, pct } from '../lib/format'

const STEPS = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-400)', 'var(--seq-550)', 'var(--seq-700)']

// DCF value per share across growth (rows) and discount rate (columns).
// Sequential one-hue ramp: darker = higher value. Every cell is a button:
// selecting one reads out that combination against today's price.
export function Sensitivity({
  grid,
  price,
}: {
  grid: Record<string, Record<string, number | null>>
  price: number
}) {
  const rows = Object.keys(grid)
  const columns = rows.length ? Object.keys(grid[rows[0]]) : []
  const values = rows.flatMap((r) => columns.map((c) => grid[r][c])).filter((v): v is number => v != null)
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const [sel, setSel] = useState<[string, string]>([rows[Math.floor(rows.length / 2)], columns[Math.floor(columns.length / 2)]])

  const step = (v: number) => Math.min(STEPS.length - 1, Math.floor(((v - lo) / (hi - lo || 1)) * STEPS.length))
  const g = (r: string) => r.replace('g=', '')
  const w = (c: string) => c.replace('WACC=', '')
  const picked = sel[0] && sel[1] ? grid[sel[0]]?.[sel[1]] : null
  const gap = picked != null ? (picked / price - 1) * 100 : null
  const above = values.filter((v) => v >= price).length

  return (
    <div className="sens">
      <div className="table-wrap">
        <table className="heat" aria-label="DCF sensitivity to growth and discount rate">
          <thead>
            <tr>
              <th scope="col">Growth \ discount rate</th>
              {columns.map((c) => <th key={c} scope="col" className="num">{w(c)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r}>
                <th scope="row">{g(r)}</th>
                {columns.map((c) => {
                  const v = grid[r][c]
                  if (v == null) return <td key={c}>n/a</td>
                  const s = step(v)
                  const on = sel[0] === r && sel[1] === c
                  return (
                    <td key={c} style={{ background: STEPS[s] }}>
                      <button type="button" className={`cell${on ? ' on' : ''}`} aria-pressed={on}
                        onClick={() => setSel([r, c])} style={{ color: s >= 2 ? '#fff' : '#0b0b0b', fontWeight: v >= price ? 700 : 400 }}
                        aria-label={`Growth ${g(r)}, discount rate ${w(c)}: ${money(v)}`}>
                        {money(v)}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sens-read" aria-live="polite">
        {picked != null && gap != null ? (
          <p>
            If cash flows grow <b>{g(sel[0])}</b> a year and investors demand <b>{w(sel[1])}</b>, the DCF says{' '}
            <b>{money(picked)}</b>, which is <span className={`delta ${gap >= 0 ? 'up' : 'down'}`}>{pct(gap, true, 0)}</span> versus today's {money(price)}.
          </p>
        ) : <p>Select a cell.</p>}
        <p className="muted small">{above} of {values.length} combinations are at or above today's price (bold cells).</p>
      </div>
    </div>
  )
}
