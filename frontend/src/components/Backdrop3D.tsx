import { useEffect, useRef } from 'react'

// Decorative only: a slowly rotating field of dots shaped like a rolling
// surface. It encodes no data, is hidden from assistive tech, freezes for
// reduced-motion users and pauses when off screen or in a background tab.
const N = 30
const TILT = 0.95
const FOCAL = 2.6

export function Backdrop3D() {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return

    const still = window.matchMedia('(prefers-reduced-motion: reduce)')
    let color = '#2a78d6'
    let w = 0
    let h = 0
    let frame = 0
    let raf = 0
    let visible = true
    const start = performance.now()

    const readColor = () => {
      color = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || color
    }

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = el.clientWidth
      h = el.clientHeight
      el.width = Math.round(w * dpr)
      el.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h)
      ctx.fillStyle = color
      const spin = t * 0.00006
      const cosA = Math.cos(spin), sinA = Math.sin(spin)
      const cosT = Math.cos(TILT), sinT = Math.sin(TILT)
      const scale = Math.min(w * 0.5, h * 0.95)

      for (let i = 0; i < N; i++) {
        for (let j = 0; j < N; j++) {
          const x = (i / (N - 1)) * 2 - 1
          const z = (j / (N - 1)) * 2 - 1
          const y = 0.2 * Math.sin(3 * x + t * 0.0005) * Math.cos(2.4 * z + t * 0.0004)

          // rotate around the vertical axis, then tilt toward the viewer
          const rx = x * cosA - z * sinA
          const rz = x * sinA + z * cosA
          const ty = y * cosT - rz * sinT
          const tz = y * sinT + rz * cosT

          const p = FOCAL / (FOCAL + tz)
          const sx = w / 2 + rx * scale * p
          const sy = h / 2 + ty * scale * p
          const depth = (1 - tz) / 2 // 0 far .. 1 near

          ctx.globalAlpha = 0.18 + depth * 0.72
          ctx.beginPath()
          ctx.arc(sx, sy, 0.7 + depth * 1.7, 0, Math.PI * 2)
          ctx.fill()
        }
      }
      ctx.globalAlpha = 1
    }

    const loop = (now: number) => {
      if (frame++ % 30 === 0) readColor()
      draw(now - start)
      raf = requestAnimationFrame(loop)
    }

    const play = () => {
      cancelAnimationFrame(raf)
      readColor()
      if (still.matches) draw(4000)
      else if (visible && !document.hidden) raf = requestAnimationFrame(loop)
    }

    resize()
    play()

    const resizer = new ResizeObserver(() => { resize(); if (still.matches) draw(4000) })
    resizer.observe(el)
    const viewer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; play() })
    viewer.observe(el)
    const theme = new MutationObserver(() => { readColor(); if (still.matches) draw(4000) })
    theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const onVisibility = () => play()
    document.addEventListener('visibilitychange', onVisibility)
    still.addEventListener('change', play)

    return () => {
      cancelAnimationFrame(raf)
      resizer.disconnect()
      viewer.disconnect()
      theme.disconnect()
      document.removeEventListener('visibilitychange', onVisibility)
      still.removeEventListener('change', play)
    }
  }, [])

  return <canvas ref={canvas} className="backdrop3d" aria-hidden="true" />
}
