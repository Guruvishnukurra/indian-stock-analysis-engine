// Round axis ticks (clean numbers, roughly `count` of them).
export function niceTicks(min: number, max: number, count: number): number[] {
  const span = max - min
  if (!(span > 0)) return [min]
  const raw = span / count
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => span / s <= count) ?? raw
  const start = Math.ceil(min / step) * step
  const ticks: number[] = []
  for (let t = start; t <= max; t += step) ticks.push(Math.round(t * 100) / 100)
  return ticks
}
