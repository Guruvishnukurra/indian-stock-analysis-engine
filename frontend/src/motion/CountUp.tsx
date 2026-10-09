import { animate, useReducedMotion } from 'motion/react'
import { useContext, useEffect, useRef, useState } from 'react'
import { StillNumbers } from './still'

const EASE_OUT = [0.16, 1, 0.3, 1] as const

/* Tweens a number into place on mount and whenever it changes. The final
   value is always what assistive tech reads; reduced-motion users see it
   immediately. */
export function CountUp({ value, format, duration = 0.9, delay = 0, from = 0 }: {
  value: number
  format: (n: number) => string
  duration?: number
  delay?: number
  from?: number
}) {
  const prefersStill = useReducedMotion()
  const onPaper = useContext(StillNumbers)
  const reduce = prefersStill || onPaper
  const [shown, setShown] = useState(from)
  const last = useRef(from)

  useEffect(() => {
    if (reduce) return
    const controls = animate(last.current, value, {
      duration, delay, ease: EASE_OUT,
      onUpdate: (n) => { last.current = n; setShown(n) },
    })
    return () => controls.stop()
  }, [value, reduce, duration, delay])

  return (
    <>
      <span aria-hidden="true">{format(reduce ? value : shown)}</span>
      <span className="visually-hidden">{format(value)}</span>
    </>
  )
}
