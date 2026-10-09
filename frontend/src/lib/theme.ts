import { useSyncExternalStore } from 'react'

export type Theme = 'light' | 'dim' | 'dark'

// One shared theme store, so the report header, the compare page and the
// command palette always agree. Dim is the default; the choice persists.
function read(): Theme {
  try {
    const saved = localStorage.getItem('theme')
    return saved === 'light' || saved === 'dark' ? saved : 'dim'
  } catch {
    return 'dim'
  }
}

let current: Theme = read()
const listeners = new Set<() => void>()

export function setTheme(t: Theme) {
  current = t
  document.documentElement.setAttribute('data-theme', t)
  try {
    localStorage.setItem('theme', t)
  } catch {
    /* storage unavailable: theme still applies for this visit */
  }
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function useTheme(): [Theme, (t: Theme) => void] {
  return [useSyncExternalStore(subscribe, () => current), setTheme]
}
