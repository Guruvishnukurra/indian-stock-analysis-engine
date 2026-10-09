import { ChartLineUp } from '@phosphor-icons/react'
import { useEffect, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router'
import { DISCLAIMER } from '../../lib/copy'

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
          <Link className="nav-cta" to="/s/TCS">Open a report</Link>
        </nav>
      </header>
      <main id={mainId}>{children}</main>
      <footer className="home-footer"><p>{DISCLAIMER}</p></footer>
    </div>
  )
}
