import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, Expand, ExternalLink } from 'lucide-react'
import type { WorkspaceEntry } from '@/api/workspace'
import {
  EMBEDDED_FRAME_HEIGHT,
  MIN_FRAME_HEIGHT,
  buildNativeDocument,
  createRenderCapability,
  parseBridgeMessage,
} from '@/lib/nativeBridge'

interface NativeEntryFrameProps {
  entry: WorkspaceEntry
  onEntry: (word: string) => void
  onRefresh?: () => void
  fullView?: boolean
}

export function NativeEntryFrame({ entry, onEntry, onRefresh, fullView = false }: NativeEntryFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const fullButtonRef = useRef<HTMLButtonElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const refreshAttempted = useRef(false)
  const [height, setHeight] = useState(fullView ? 720 : 420)
  const [bridgeReady, setBridgeReady] = useState(false)
  const [degraded, setDegraded] = useState(false)
  const [fullSourceOpen, setFullSourceOpen] = useState(false)
  const capability = useMemo(() => createRenderCapability(), [entry.key, entry.html])
  const documentHtml = useMemo(
    () => buildNativeDocument(entry.html, capability),
    [entry.html, capability],
  )

  useEffect(() => {
    setBridgeReady(false)
    setDegraded(false)
    refreshAttempted.current = false
    const timeout = window.setTimeout(() => setDegraded(true), 1_500)
    return () => window.clearTimeout(timeout)
  }, [capability])

  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return
      if (event.origin !== 'null') return
      const message = parseBridgeMessage(event.data, capability)
      if (!message) return
      if (message.type === 'ready') {
        setBridgeReady(true)
        setDegraded(false)
      } else if (message.type === 'height') {
        setHeight(Math.max(MIN_FRAME_HEIGHT, message.payload.height))
      } else if (message.type === 'entry') {
        onEntry(message.payload.word)
      } else if (message.type === 'sound' || message.type === 'media') {
        const audio = new Audio(message.payload.url)
        void audio.play().catch(() => setDegraded(true))
      } else if (message.type === 'resource-error' && !refreshAttempted.current) {
        refreshAttempted.current = true
        onRefresh?.()
      }
    }
    window.addEventListener('message', receive)
    return () => window.removeEventListener('message', receive)
  }, [capability, onEntry, onRefresh])

  useEffect(() => {
    if (fullSourceOpen) {
      dialogRef.current?.showModal()
      window.setTimeout(() => closeButtonRef.current?.focus(), 0)
    } else {
      if (dialogRef.current?.open) dialogRef.current.close()
      fullButtonRef.current?.focus({ preventScroll: true })
    }
  }, [fullSourceOpen])

  const embeddedHeight = fullView ? Math.min(height, 8_000) : Math.min(height, EMBEDDED_FRAME_HEIGHT)
  const oversized = !fullView && height > EMBEDDED_FRAME_HEIGHT

  return (
    <>
      <div className={`native-frame-shell ${degraded ? 'is-degraded' : ''}`}>
        <iframe
          ref={iframeRef}
          title={`${entry.sourceTitle}: ${entry.headword}`}
          srcDoc={documentHtml}
          sandbox="allow-scripts"
          referrerPolicy="no-referrer"
          className="native-frame"
          style={{ height: `${bridgeReady ? embeddedHeight : Math.min(560, embeddedHeight)}px` }}
          tabIndex={0}
        />
        {degraded && (
          <div className="native-frame-notice" role="status">
            <AlertTriangle size={15} />
            Native sizing or media is degraded. The entry remains readable in a bounded frame.
          </div>
        )}
      </div>
      {(oversized || degraded) && !fullView && (
        <button ref={fullButtonRef} className="source-view-button" onClick={() => setFullSourceOpen(true)}>
          <Expand size={15} /> Full source view
        </button>
      )}
      {fullSourceOpen && (
        <dialog
          ref={dialogRef}
          className="source-dialog"
          aria-label={`${entry.sourceTitle} full source`}
          onCancel={(event) => {
            event.preventDefault()
            setFullSourceOpen(false)
          }}
          onClose={() => setFullSourceOpen(false)}
        >
            <header className="source-dialog-header">
              <div>
                <span className="eyebrow">Safe source view</span>
                <h2>{entry.sourceTitle}</h2>
              </div>
              <button ref={closeButtonRef} className="secondary-button" onClick={() => setFullSourceOpen(false)}>
                Return to results
              </button>
            </header>
            <NativeEntryFrame entry={entry} onEntry={onEntry} onRefresh={onRefresh} fullView />
            {entry.citation && (
              <a className="citation-link" href={`#${entry.key}`} onClick={(event) => event.preventDefault()}>
                <ExternalLink size={13} /> {entry.citation.uri}
              </a>
            )}
        </dialog>
      )}
    </>
  )
}

export function LegacyEntryFrame({ entry }: { entry: WorkspaceEntry }) {
  return (
    <div className="legacy-frame-shell">
      <iframe
        title={`${entry.sourceTitle}: legacy inert rendering`}
        srcDoc={entry.html}
        sandbox=""
        referrerPolicy="no-referrer"
        className="native-frame legacy-frame"
      />
      <div className="native-frame-notice" role="status">
        Legacy fallback: scripts and interactions are disabled. Configure a v2 token for the secure native bridge.
      </div>
    </div>
  )
}
