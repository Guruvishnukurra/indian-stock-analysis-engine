// The command palette lives once at the app root; anything can open it.
const EVENT = 'open-command-palette'

export function openPalette() {
  window.dispatchEvent(new Event(EVENT))
}

export function onOpenPalette(handler: () => void) {
  window.addEventListener(EVENT, handler)
  return () => window.removeEventListener(EVENT, handler)
}
