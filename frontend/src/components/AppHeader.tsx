import { ChartLineUp, CircleHalf, Command, Moon, Sun } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { openPalette } from '../lib/palette'
import { type Theme, useTheme } from '../lib/theme'

const THEMES: { id: Theme; label: string; Icon: typeof Sun }[] = [
  { id: 'light', label: 'Light theme', Icon: Sun },
  { id: 'dim', label: 'Dim theme (default)', Icon: CircleHalf },
  { id: 'dark', label: 'Dark theme', Icon: Moon },
]

function ThemeControl() {
  const [theme, setTheme] = useTheme()
  return (
    <div className="segmented" role="radiogroup" aria-label="Colour theme">
      {THEMES.map(({ id, label, Icon }) => (
        <button key={id} type="button" role="radio" aria-checked={theme === id} aria-label={label}
          title={label} onClick={() => setTheme(id)}>
          <Icon size={16} weight={theme === id ? 'fill' : 'regular'} />
        </button>
      ))}
    </div>
  )
}

/* Header for the working pages (report, compare). */
export function AppHeader({ center, actions }: { center?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="appbar">
      <div className={`appbar-inner${center ? '' : ' no-center'}`}>
        <Link className="brand" to="/">
          <span className="brand-mark" aria-hidden="true"><ChartLineUp size={18} weight="bold" /></span>
          <span className="brand-name">Stock Analysis Engine</span>
        </Link>
        {center}
        <div className="bar-actions">
          {actions}
          <button type="button" className="btn btn-ghost palette-btn" onClick={openPalette} aria-label="Open the command palette" title="Command palette (Ctrl+K)">
            <Command size={16} aria-hidden="true" /><kbd aria-hidden="true">Ctrl K</kbd>
          </button>
          <ThemeControl />
        </div>
      </div>
    </header>
  )
}
