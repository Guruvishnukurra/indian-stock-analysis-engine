import { money } from '../lib/format'

const STEPS = ['var(--seq-100)', 'var(--seq-250)', 'var(--seq-400)', 'var(--seq-550)', 'var(--seq-700)']

// DCF value per share across growth (rows) and discount rate (columns).
// Sequential one-hue ramp: darker = higher value. Values are printed in
// every cell (it is a small table), with ink chosen for contrast.
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

  const step = (v: number) => Math.min(STEPS.length - 1, Math.floor(((v - lo) / (hi - lo || 1)) * STEPS.length))

  return (
    <div className="table-wrap">
      <table className="heat" aria-label="DCF sensitivity to growth and discount rate">
        <thead>
          <tr>
            <th scope="col">Growth \ discount rate</th>
            {columns.map((c) => <th key={c} scope="col" className="num">{c.replace('WACC=', '')}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th scope="row">{r.replace('g=', '')}</th>
              {columns.map((c) => {
                const v = grid[r][c]
                if (v == null) return <td key={c}>n/a</td>
                const s = step(v)
                return (
                  <td key={c} title={`${r}, ${c}: ${money(v)}${v >= price ? ' (at or above price)' : ''}`}
                    style={{ background: STEPS[s], color: s >= 2 ? '#fff' : '#0b0b0b', fontWeight: v >= price ? 700 : 400 }}>
                    {money(v)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">Bold cells are at or above today's price ({money(price)}).</p>
    </div>
  )
}
