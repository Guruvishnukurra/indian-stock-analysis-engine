import { useLayoutEffect, useState, type RefObject } from 'react'

// Tracks an element's rendered width so charts draw in real pixels and
// their text stays the same size at every screen width.
export function useWidth(ref: RefObject<HTMLElement | null>, fallback = 760) {
  const [width, setWidth] = useState(fallback)

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setWidth(Math.max(Math.round(el.clientWidth), 280))
    update()
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])

  return width
}
