import { useLayoutEffect, useRef } from 'react'

/* A selection indicator that slides to the active button. Place it as a
   direct child of the control; it measures the index-th direct child
   button (no layout projection, so sticky or scrolled containers cannot
   throw it off). Only compositor-friendly properties animate:
   - "line": translateX + scaleX of a 100px bar (thin, so scaling is invisible)
   - "pill": a full-size layer revealed by clip-path inset, so corners stay true
   `inset` trims each side of a line. */
export function SlideIndicator({ index, className, kind, inset = 0 }: {
  index: number; className: string; kind: 'line' | 'pill'; inset?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    const parent = el?.parentElement
    if (!el || !parent) return
    const measure = () => {
      const button = parent.querySelectorAll<HTMLElement>(':scope > button')[index]
      if (!button) return
      if (kind === 'line') {
        const width = Math.max(0, button.offsetWidth - inset * 2)
        el.style.transform = `translateX(${button.offsetLeft + inset}px) scaleX(${width / 100})`
      } else {
        const right = parent.clientWidth - button.offsetLeft - button.offsetWidth
        el.style.clipPath = `inset(${button.offsetTop}px ${right}px ${parent.clientHeight - button.offsetTop - button.offsetHeight}px ${button.offsetLeft}px round 8px)`
      }
      el.style.opacity = '1'
      // enable the transition only after the first placement, so it never slides in from 0
      requestAnimationFrame(() => { el.dataset.ready = 'true' })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(parent)
    return () => observer.disconnect()
  }, [index, inset, kind])

  return <span ref={ref} className={className} aria-hidden="true" style={{ opacity: 0 }} />
}
