import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
interface Props { titleId: string; className: string; onClose: () => void; children: ReactNode }
export function Dialog({ titleId, className, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const dialog = ref.current!
    dialog.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      dialog.close()
      document.body.style.overflow = previousOverflow
      if (opener?.isConnected && document.activeElement === document.body) opener.focus()
    }
  }, [])
  return createPortal(<dialog ref={ref} aria-labelledby={titleId} className={className} onKeyDown={event => {
    if (event.key !== 'Tab') return
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]')).filter(node => node.getClientRects().length > 0)
    const first = controls[0], last = controls[controls.length - 1]
    if (!first) { event.preventDefault(); event.currentTarget.focus(); return }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }} onCancel={event => { event.preventDefault(); close.current() }} onClick={event => { if (event.target === event.currentTarget) { const box = event.currentTarget.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close.current() } }}>{children}</dialog>, document.body)
}
