import { X } from '@phosphor-icons/react'
import { useEffect, useRef, type ReactNode } from 'react'

// Side sheet built on the native <dialog>: focus trap, Escape to close and
// an inert page behind it come from the browser, not from custom code.
export function Drawer({ open, title, eyebrow, onClose, children }: {
  open: boolean; title: string; eyebrow?: string; onClose: () => void; children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={ref} className="drawer" aria-labelledby="drawer-title" onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose() }}>
      <div className="drawer-inner">
        <div className="drawer-head">
          <div>
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            <h2 id="drawer-title">{title}</h2>
          </div>
          <button type="button" className="btn btn-ghost btn-icon" onClick={onClose} aria-label="Close details">
            <X size={18} />
          </button>
        </div>
        <div className="drawer-body">{open && children}</div>
      </div>
    </dialog>
  )
}
