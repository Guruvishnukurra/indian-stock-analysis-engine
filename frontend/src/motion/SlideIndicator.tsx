import { useLayoutEffect, useRef } from 'react'

/* A selection indicator that slides to the active button. Place it as a
   direct child of the control; it measures the index-th direct child
   button and moves with a CSS transition (no layout projection, so sticky
   or scrolled containers cannot throw it off). `inset` trims each side. */
export function SlideIndicator({ index, className, inset = 0 }: { index: number; className: string; inset?: number }) {
  const ref = useRef<HTMLSpanElement>(null)

  useLayoutEffect(() => {
    const el = ref.current
    const parent = el?.parentElement
    if (!el || !parent) return
    const measure = () => {
      const button = parent.querySelectorAll<HTMLElement>(':scope > button')[index]
      if (!button) return
      el.style.transform = `translateX(${button.offsetLeft + inset}px)`
      el.style.width = `${Math.max(0, button.offsetWidth - inset * 2)}px`
      el.style.opacity = '1'
      // enable the transition only after the first placement, so it never slides in from 0
      requestAnimationFrame(() => { el.dataset.ready = 'true' })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(parent)
    return () => observer.disconnect()
  }, [index, inset])

  return <span ref={ref} className={className} aria-hidden="true" style={{ opacity: 0 }} />
}
