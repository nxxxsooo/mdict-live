import { useEffect, useRef } from 'react'
import { Bot, Quote, X } from 'lucide-react'
import type { WorkspaceLookup } from '@/api/workspace'
import { useAppStore } from '@/stores/useAppStore'

interface ContextDrawerProps {
  lookup?: WorkspaceLookup
  returnFocusRef: React.RefObject<HTMLButtonElement | null>
}

export function ContextDrawer({ lookup, returnFocusRef }: ContextDrawerProps) {
  const open = useAppStore((state) => state.contextOpen)
  const setOpen = useAppStore((state) => state.setContextOpen)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    if (open) closeButtonRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (open) dialogRef.current?.showModal()
  }, [open])

  if (!open) return null
  const evidence = lookup?.entries.flatMap((entry) =>
    entry.textBlocks.slice(0, 2).map((block) => ({ source: entry.sourceTitle, block })),
  ) ?? []
  const close = () => {
    setOpen(false)
    window.setTimeout(() => returnFocusRef.current?.focus(), 0)
  }

  return (
      <dialog
        ref={dialogRef}
        className="context-drawer"
        aria-label="Context and agent guidance"
        onCancel={(event) => { event.preventDefault(); close() }}
        onClose={close}
      >
        <header>
          <div><span className="eyebrow">Context</span><h2>Evidence before inference</h2></div>
          <button ref={closeButtonRef} className="icon-button" aria-label="Close context panel" onClick={close}><X size={18} /></button>
        </header>
        <section className="context-section">
          <div className="context-heading"><Quote size={16} /><strong>Retrieved evidence</strong></div>
          {evidence.length > 0 ? evidence.map(({ source, block }) => (
            <blockquote key={block.blockId}>
              <p>{block.text}</p>
              <cite>{source} · {block.citation.uri}</cite>
            </blockquote>
          )) : <p className="muted-copy">No citable text block is available for this lookup.</p>}
        </section>
        <section className="agent-placeholder">
          <Bot size={20} />
          <div><strong>Agent bundle not connected</strong><p>Deterministic lookup remains complete. Install the optional Pi bundle to explain a word in context using these citations.</p></div>
        </section>
      </dialog>
  )
}
