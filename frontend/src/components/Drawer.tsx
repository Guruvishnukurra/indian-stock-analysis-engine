import { X } from '@phosphor-icons/react'
import { useLayoutEffect, useRef, type ReactNode } from 'react'

// Side sheet built on the native <dialog>: focus trap, Escape to close and
// an inert page behind it come from the browser, not from custom code.
// Opens in a layout effect so a figure flying in can measure its target.
export function Drawer({ open, title, figure, flight = false, onClose, children }: {
  open: boolean
  title: string
  figure?: ReactNode
  flight?: boolean
  onClose: () => void
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useLayoutEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={ref} className={`drawer${flight ? ' flight' : ''}`} aria-labelledby="drawer-title" onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose() }}>
      <div className="drawer-inner">
        <div className="drawer-head">
          <div className="drawer-heading">
            <h2 id="drawer-title">{title}</h2>
            {open && figure}
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
