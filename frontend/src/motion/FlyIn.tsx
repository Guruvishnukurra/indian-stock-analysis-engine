import { useReducedMotion } from 'motion/react'
import { useLayoutEffect, useRef, type ReactNode } from 'react'

/* FLIP flight: the clicked figure appears to travel from where it was on
   the page into the panel header. `origin` is the clicked figure's rect.
   Measured after the panel opens (a microtask after layout), so the
   <dialog> is already in the top layer. */
export function FlyIn({ origin, children }: { origin: DOMRect | null; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()

  useLayoutEffect(() => {
    const el = ref.current
    if (!el || !origin || reduce) return
    let cancelled = false
    queueMicrotask(() => {
      if (cancelled) return
      const target = el.getBoundingClientRect()
      if (!target.height) return
      const scale = origin.height / target.height
      el.animate(
        [
          { transform: `translate(${origin.left - target.left}px, ${origin.top - target.top}px) scale(${scale})` },
          { transform: 'none' },
        ],
        { duration: 720, easing: 'cubic-bezier(0.16, 1, 0.3, 1)' },
      )
    })
    return () => { cancelled = true }
  }, [origin, reduce])

  return <div ref={ref} className="drawer-figure">{children}</div>
}
