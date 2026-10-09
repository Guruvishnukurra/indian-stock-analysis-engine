import {
  ArrowRight,
  BookOpen,
  FilePdf,
  ChartLineUp,
  CircleHalf,
  Columns,
  House,
  Lightning,
  Moon,
  Scales,
  Sun,
  TreeStructure,
} from '@phosphor-icons/react'
import { Command } from 'cmdk'
import { useEffect, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { type DemoItem, bareSymbol, getManifest } from '../lib/demo'
import { onOpenPalette } from '../lib/palette'
import { setTheme } from '../lib/theme'

const TICKER = /^[A-Z0-9&-]{1,20}$/

const EXPLAIN: [string, string][] = [
  ['stance', 'How the stance was decided'],
  ['fairvalue', 'How the fair value was built'],
  ['upside', 'From fair value to upside'],
  ['confidence', 'Why this confidence score'],
  ['quality', 'How quality was scored'],
  ['timing', 'How timing was read'],
]

const SECTIONS: [string, string][] = [
  ['overview', 'Overview'], ['valuation', 'Valuation'], ['fundamentals', 'Fundamentals'], ['market', 'Market'], ['news', 'News and risks'],
]

function Item({ icon, children, hint, onSelect, value, keywords }: {
  icon: ReactNode; children: ReactNode; hint?: string; onSelect: () => void; value: string; keywords?: string[]
}) {
  return (
    <Command.Item value={value} keywords={keywords} onSelect={onSelect}>
      <span className="cp-ic" aria-hidden="true">{icon}</span>
      <span className="cp-text">{children}</span>
      {hint && <span className="cp-hint">{hint}</span>}
    </Command.Item>
  )
}

/* Ctrl+K / Cmd+K from anywhere: companies, report sections, traces, pages, theme. */
export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<DemoItem[]>([])
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    const off = onOpenPalette(() => setOpen(true))
    return () => { window.removeEventListener('keydown', onKey); off() }
  }, [])

  useEffect(() => { if (open) getManifest().then((m) => setItems(m.items)) }, [open])

  const go = (to: string) => { setOpen(false); setQuery(''); navigate(to) }
  const report = location.pathname.match(/^\/s\/([^/]+)/)?.[1]
  const current = report ? bareSymbol(decodeURIComponent(report)) : null
  const typed = bareSymbol(query)
  const offerLive = TICKER.test(typed) && !items.some((i) => i.symbol === typed)
  const reportUrl = (patch: Record<string, string>) => {
    const p = new URLSearchParams(location.search)
    Object.entries(patch).forEach(([k, v]) => p.set(k, v))
    return `/s/${current}?${p}`
  }

  return (
    <Command.Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) setQuery('') }} label="Command palette"
      className="cp" overlayClassName="cp-overlay" contentClassName="cp-content">
      <Command.Input value={query} onValueChange={setQuery} placeholder="Search companies, sections and explanations" />
      <Command.List>
        <Command.Empty>No match. Type an NSE ticker to analyse it live.</Command.Empty>

        {offerLive && (
          <Command.Group heading="Analyse">
            <Item value={`analyse ${typed}`} icon={<Lightning size={16} />} hint="Live engine" onSelect={() => go(`/s/${typed}`)}>
              Analyse {typed}
            </Item>
          </Command.Group>
        )}

        {current && (
          <Command.Group heading={`This report: ${current}`}>
            {EXPLAIN.map(([id, label]) => (
              <Item key={id} value={`explain ${label}`} keywords={['explain', 'trace', 'why']} icon={<TreeStructure size={16} />}
                hint="Explain" onSelect={() => go(reportUrl({ explain: id }))}>{label}</Item>
            ))}
            <Item value="download pdf report" keywords={['pdf', 'download', 'print', 'report', 'export']} icon={<FilePdf size={16} />}
              hint="PDF" onSelect={() => go(`/s/${current}/report`)}>Download the PDF report</Item>
            {SECTIONS.map(([id, label]) => (
              <Item key={id} value={`section ${label}`} keywords={['tab', 'section']} icon={<ArrowRight size={16} />}
                hint="Section" onSelect={() => go(`/s/${current}?tab=${id}`)}>{label}</Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Showcase companies">
          {items.map((i) => (
            <Item key={i.symbol} value={`${i.symbol} ${i.name ?? ''}`} keywords={[i.description ?? '']}
              icon={<ChartLineUp size={16} />} hint={i.description} onSelect={() => go(`/s/${i.symbol}`)}>
              <b>{i.symbol}</b> <span className="cp-sub">{i.name}</span>
            </Item>
          ))}
        </Command.Group>

        {current && (
          <Command.Group heading="Compare">
            {items.filter((i) => i.symbol !== current).slice(0, 4).map((i) => (
              <Item key={i.symbol} value={`compare ${current} ${i.symbol}`} keywords={['compare', 'versus']}
                icon={<Columns size={16} />} onSelect={() => go(`/compare?a=${current}&b=${i.symbol}`)}>
                Compare {current} with {i.symbol}
              </Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Pages">
          <Item value="home" icon={<House size={16} />} onSelect={() => go('/')}>Home</Item>
          <Item value="how it works" keywords={['method', 'methodology', 'story']} icon={<BookOpen size={16} />} onSelect={() => go('/how-it-works')}>How it works</Item>
          <Item value="evidence" keywords={['validation', 'tests', 'ml']} icon={<Scales size={16} />} onSelect={() => go('/evidence')}>Evidence</Item>
          <Item value="compare page" keywords={['compare', 'versus']} icon={<Columns size={16} />} onSelect={() => go('/compare')}>Compare two companies</Item>
        </Command.Group>

        <Command.Group heading="Theme">
          <Item value="theme light" icon={<Sun size={16} />} onSelect={() => { setTheme('light'); setOpen(false) }}>Light theme</Item>
          <Item value="theme dim" icon={<CircleHalf size={16} />} onSelect={() => { setTheme('dim'); setOpen(false) }}>Dim theme</Item>
          <Item value="theme dark" icon={<Moon size={16} />} onSelect={() => { setTheme('dark'); setOpen(false) }}>Dark theme</Item>
        </Command.Group>
      </Command.List>
      <div className="cp-foot" aria-hidden="true"><kbd>↑</kbd><kbd>↓</kbd> to move <kbd>Enter</kbd> to open <kbd>Esc</kbd> to close</div>
    </Command.Dialog>
  )
}
