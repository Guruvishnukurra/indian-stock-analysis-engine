import { ChartLineUp, MagnifyingGlass } from '@phosphor-icons/react'
import { useEffect, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { DISCLAIMER } from '../../lib/copy'
import { openPalette } from '../../lib/palette'

/* Frame for the story pages (home, how it works, evidence): always bright,
   whatever theme the working report uses. */
export function StoryShell({ children, mainId = 'story-main' }: { children: ReactNode; mainId?: string }) {
  useEffect(() => {
    document.documentElement.dataset.surface = 'story'
    return () => { delete document.documentElement.dataset.surface }
  }, [])

  return (
    <div className="story">
      <a className="skip-link" href={`#${mainId}`}>Skip to content</a>
      <header className="home-nav">
        <Link className="home-brand" to="/">
          <span className="brand-mark" aria-hidden="true"><ChartLineUp size={18} weight="bold" /></span>
          Stock Analysis Engine
        </Link>
        <nav aria-label="Main">
          <NavLink to="/how-it-works">How it works</NavLink>
          <NavLink to="/evidence">Evidence</NavLink>
          <NavLink to="/compare">Compare</NavLink>
          <button type="button" className="nav-search" onClick={openPalette} aria-label="Search (Ctrl+K)" title="Search (Ctrl+K)">
            <MagnifyingGlass size={16} aria-hidden="true" /><kbd aria-hidden="true">Ctrl K</kbd>
          </button>
          <NavLink className="nav-report" to="/s/TCS">Open a report</NavLink>
        </nav>
      </header>
      <main id={mainId}>{children}</main>
      <footer className="home-footer"><p>{DISCLAIMER}</p></footer>
    </div>
  )
}
