import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dim' | 'dark'

// Dim is the default working theme; the choice persists per browser.
export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const saved = localStorage.getItem('theme')
      return saved === 'light' || saved === 'dark' ? saved : 'dim'
    } catch {
      return 'dim'
    }
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* storage unavailable: theme still applies for this visit */
    }
  }, [theme])

  return [theme, setTheme]
}
