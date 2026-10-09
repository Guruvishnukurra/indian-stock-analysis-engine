import { useEffect, useRef, type RefObject } from 'react'

/* The home hero's light: simulated price paths fanning out of the search
   field. Geometric Brownian motion, indexed to ₹100 today, 5 years monthly.
   Paths are coloured by final outcome; the 10th/50th/90th percentile lines
   are drawn on top and labelled at the right edge. Changing `sigma` morphs
   the whole fan to the new spread. Purely illustrative, never a forecast. */

const N = 150
const STEPS = 60
const MU = 0.1
const MAX_LN = 1.8 // vertical scale fixed so a wider sigma visibly widens the fan

type Sim = { v: Float32Array; rank: Float32Array }

function rng(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// Stored as log(value / 100) so morphs interpolate smoothly.
function simulate(sigma: number, seed: number): Sim {
  const r = rng(seed)
  const gauss = () => Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(2 * Math.PI * r())
  const dt = 1 / 12
  const v = new Float32Array(N * (STEPS + 1))
  for (let p = 0; p < N; p++) {
    let x = 0
    for (let t = 1; t <= STEPS; t++) {
      x += (MU - 0.5 * sigma * sigma) * dt + sigma * Math.sqrt(dt) * gauss()
      v[p * (STEPS + 1) + t] = x
    }
  }
  const order = Array.from({ length: N }, (_, p) => p).sort((a, b) => v[a * (STEPS + 1) + STEPS] - v[b * (STEPS + 1) + STEPS])
  const rank = new Float32Array(N)
  order.forEach((p, i) => { rank[p] = i / (N - 1) })
  return { v, rank }
}

const LOW = [255, 106, 61], MID = [57, 135, 229], HIGH = [25, 184, 132]
function mix(a: number[], b: number[], t: number) { return a.map((x, i) => Math.round(x + (b[i] - x) * t)) }
function outcome(f: number) { return f < 0.5 ? mix(LOW, MID, f / 0.5) : mix(MID, HIGH, (f - 0.5) / 0.5) }

const ease = (t: number) => 1 - Math.pow(1 - t, 3)

export function FanCanvas({ originRef, sigma, onRange }: {
  originRef: RefObject<HTMLElement | null>
  sigma: number
  onRange?: (r: { p10: number; p50: number; p90: number }) => void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const target = useRef(sigma)
  useEffect(() => { target.current = sigma }, [sigma])

  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return

    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let w = 0, h = 0, ox = 0, oy = 0, scale = 1, top = 0, bottom = 0
    let seed = 11
    let shownSigma = target.current
    let from = simulate(shownSigma, seed)
    let to = from
    let morphStart = -1
    const born = performance.now()
    let lastResample = born
    let raf = 0
    let reported = ''
    let visible = true

    const layout = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      const box = el.getBoundingClientRect()
      w = box.width; h = box.height
      el.width = Math.round(w * dpr); el.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      const anchor = originRef.current?.getBoundingClientRect()
      if (anchor && w >= 900) {
        ox = anchor.right - box.left + 18
        oy = anchor.top - box.top + anchor.height / 2
        top = 92
        bottom = h - 170
        scale = Math.min(oy - top, bottom - oy) / MAX_LN
      } else if (anchor) {
        // narrow screens: the fan opens in the space reserved under the search field
        ox = anchor.left - box.left + 6
        top = anchor.bottom - box.top + 18
        bottom = top + 198
        oy = (top + bottom) / 2
        scale = (bottom - oy) / MAX_LN
      }
    }

    const percentiles = (sim: Sim, k: number, t: number) => {
      const col = Array.from({ length: N }, (_, p) => {
        const a = from.v[p * (STEPS + 1) + t], b = sim.v[p * (STEPS + 1) + t]
        return a + (b - a) * k
      }).sort((a, b) => a - b)
      return [col[Math.floor(N * 0.1)], col[Math.floor(N * 0.5)], col[Math.floor(N * 0.9)]]
    }

    const draw = (now: number) => {
      ctx.clearRect(0, 0, w, h)
      const reveal = still ? 1 : ease(Math.min(1, (now - born) / 1800))
      const k = morphStart < 0 ? 1 : ease(Math.min(1, (now - morphStart) / 1100))
      if (k >= 1 && morphStart >= 0) { from = to; morphStart = -1 }
      const right = w - (w >= 900 ? 132 : 92)
      const X = (t: number) => ox + (t / STEPS) * (right - ox)
      const Y = (x: number) => oy - x * scale
      const last = Math.max(1, Math.floor(reveal * STEPS))
      const value = (p: number, t: number) => {
        const a = from.v[p * (STEPS + 1) + t], b = to.v[p * (STEPS + 1) + t]
        return a + (b - a) * k
      }

      // percentile band
      const bands = Array.from({ length: last + 1 }, (_, t) => percentiles(to, k, t))
      ctx.beginPath()
      bands.forEach(([, , p90], t) => (t ? ctx.lineTo(X(t), Y(p90)) : ctx.moveTo(X(t), Y(p90))))
      for (let t = last; t >= 0; t--) ctx.lineTo(X(t), Y(bands[t][0]))
      ctx.closePath()
      const fill = ctx.createLinearGradient(ox, 0, right, 0)
      fill.addColorStop(0, 'rgba(57,135,229,0.02)')
      fill.addColorStop(1, 'rgba(57,135,229,0.12)')
      ctx.fillStyle = fill
      ctx.fill()

      // paths
      ctx.lineWidth = 1.2
      for (let p = 0; p < N; p++) {
        const f = k < 1 ? to.rank[p] : from.rank[p]
        const [r, g, b] = outcome(f)
        const alpha = 0.2 + 0.26 * Math.abs(f - 0.5) * 2
        const grad = ctx.createLinearGradient(ox, 0, X(last), 0)
        grad.addColorStop(0, `rgba(${r},${g},${b},0)`)
        grad.addColorStop(0.25, `rgba(${r},${g},${b},${alpha * 0.6})`)
        grad.addColorStop(1, `rgba(${r},${g},${b},${alpha})`)
        ctx.strokeStyle = grad
        ctx.beginPath()
        ctx.moveTo(X(0), Y(0))
        for (let t = 1; t <= last; t++) ctx.lineTo(X(t), Y(value(p, t)))
        ctx.stroke()
      }

      // percentile lines and labels
      const lines: [number, string, string, number][] = [[2, '#0f7a58', '90th pct', 2], [1, '#0b1b33', 'Median', 2.6], [0, '#c2410c', '10th pct', 2]]
      for (const [i, color, , width] of lines) {
        ctx.strokeStyle = color
        ctx.lineWidth = width
        ctx.beginPath()
        bands.forEach((b, t) => (t ? ctx.lineTo(X(t), Y(b[i])) : ctx.moveTo(X(t), Y(b[i]))))
        ctx.stroke()
      }
      // fade everything out at the bounds so wide fans never run under the copy
      ctx.save()
      ctx.globalCompositeOperation = 'destination-in'
      const mask = ctx.createLinearGradient(0, top - 40, 0, bottom + 40)
      mask.addColorStop(0, 'rgba(0,0,0,0)')
      mask.addColorStop(0.12, 'rgba(0,0,0,1)')
      mask.addColorStop(0.88, 'rgba(0,0,0,1)')
      mask.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = mask
      ctx.fillRect(0, 0, w, h)
      ctx.restore()

      if (reveal >= 1) {
        ctx.font = '500 12px "Geist Mono", ui-monospace, monospace'
        ctx.textBaseline = 'middle'
        const end = bands[last]
        const rupees = end.map((x) => Math.round(100 * Math.exp(x)))
        let prevY = -Infinity
        for (const [i, color, label] of lines) {
          const y = Math.min(bottom - 4, Math.max(Y(end[i]), prevY + 30, top + 4))
          prevY = y
          ctx.fillStyle = color
          ctx.fillText(`₹${rupees[i]}`, right + 12, y - 7)
          ctx.fillStyle = 'rgba(11,27,51,0.6)'
          ctx.fillText(label, right + 12, y + 8)
        }
        // The caption reports exactly the figures drawn here, once a morph has settled.
        const key = rupees.join('/')
        if (morphStart < 0 && key !== reported) {
          reported = key
          onRange?.({ p10: rupees[0], p50: rupees[1], p90: rupees[2] })
        }
      }

      // today marker
      ctx.fillStyle = '#0b1b33'
      ctx.beginPath(); ctx.arc(X(0), Y(0), 4.5, 0, Math.PI * 2); ctx.fill()
      ctx.strokeStyle = 'rgba(11,27,51,0.18)'
      ctx.lineWidth = 6
      ctx.beginPath(); ctx.arc(X(0), Y(0), 9, 0, Math.PI * 2); ctx.stroke()
    }

    const morphTo = (sigmaNext: number, seedNext: number, now: number) => {
      const k = morphStart < 0 ? 1 : ease(Math.min(1, (now - morphStart) / 1100))
      if (k < 1) {
        // freeze the in-between state as the new starting point
        const mid = new Float32Array(from.v.length)
        for (let i = 0; i < mid.length; i++) mid[i] = from.v[i] + (to.v[i] - from.v[i]) * k
        from = { v: mid, rank: to.rank }
      } else from = to
      to = simulate(sigmaNext, seedNext)
      shownSigma = sigmaNext
      morphStart = now
    }

    const loop = (now: number) => {
      if (Math.abs(target.current - shownSigma) > 1e-4) { morphTo(target.current, seed, now); lastResample = now }
      else if (now - lastResample > 7000 && morphStart < 0) { seed += 1; morphTo(shownSigma, seed, now); lastResample = now }
      draw(now)
      raf = requestAnimationFrame(loop)
    }

    const play = () => {
      cancelAnimationFrame(raf)
      if (still) {
        if (Math.abs(target.current - shownSigma) > 1e-4) { to = from = simulate(target.current, seed); shownSigma = target.current }
        draw(performance.now())
      } else if (visible && !document.hidden) raf = requestAnimationFrame(loop)
    }

    layout()
    morphTo(shownSigma, seed, born); from = to; morphStart = -1
    // At rest the labels show these exact percentiles, so the caption can have them before the reveal ends.
    {
      const [p10, p50, p90] = percentiles(to, 1, STEPS).map((x) => Math.round(100 * Math.exp(x)))
      reported = `${p10}/${p50}/${p90}`
      onRange?.({ p10, p50, p90 })
    }
    play()

    const ro = new ResizeObserver(() => { layout(); if (still) draw(performance.now()) })
    ro.observe(el)
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; play() })
    io.observe(el)
    const onVis = () => play()
    document.addEventListener('visibilitychange', onVis)
    const id = still ? window.setInterval(play, 300) : 0

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect(); io.disconnect()
      document.removeEventListener('visibilitychange', onVis)
      window.clearInterval(id)
    }
  }, [originRef, onRange])

  return <canvas ref={canvas} className="fan-canvas" aria-hidden="true" />
}
