import { createContext } from 'react'

// Inside a provider set to true (the printable report), animated numbers
// render their final value immediately: paper must never show a mid-count.
export const StillNumbers = createContext(false)
