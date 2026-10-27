import { useEffect, useRef, useState } from 'react'
import { BookMarked, BookOpen, ChevronLeft, Clock3, Library, Trash2, X } from 'lucide-react'
import type { WorkspaceLookup, WorkspaceSource } from '@/api/workspace'
import {
  useClearHistory,
  useDeleteWordbookEntry,
  useHistory,
  useWordbookEntries,
  useWordbooks,
} from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'

type LedgerTab = 'sources' | 'saved' | 'history'

interface SourceLedgerProps {
  sources: WorkspaceSource[]
  lookup?: WorkspaceLookup
  loading: boolean
  returnFocusRef: React.RefObject<HTMLButtonElement | null>
}

export function SourceLedger({ sources, lookup, loading, returnFocusRef }: SourceLedgerProps) {
  const [tab, setTab] = useState<LedgerTab>('sources')
  const [wordbookId, setWordbookId] = useState<number | null>(null)
  const sidebarOpen = useAppStore((state) => state.sidebarOpen)
  const setSidebarOpen = useAppStore((state) => state.setSidebarOpen)
  const setSearchWord = useAppStore((state) => state.setSearchWord)
  const asideRef = useRef<HTMLElement>(null)
  const { data: history = [] } = useHistory()
  const clearHistory = useClearHistory()
  const { data: wordbooks = [] } = useWordbooks()
  const { data: entries = [] } = useWordbookEntries(wordbookId ?? 0)
  const deleteEntry = useDeleteWordbookEntry()
  const entrySourceIds = new Set(lookup?.entries.map((entry) => entry.sourceId) ?? [])
  const failedSourceIds = new Set(lookup?.failures.map((failure) => failure.sourceId) ?? [])

  useEffect(() => {
    const media = window.matchMedia('(min-width: 960px)')
    const updateInert = () => {
      if (asideRef.current) asideRef.current.inert = !media.matches && !sidebarOpen
    }
    updateInert()
    media.addEventListener('change', updateInert)
    return () => media.removeEventListener('change', updateInert)
  }, [sidebarOpen])

  useEffect(() => {
    const openSaved = () => {
      setTab('saved')
      if (!window.matchMedia('(min-width: 960px)').matches) setSidebarOpen(true)
    }
    window.addEventListener('mdict-open-saved', openSaved)
    return () => window.removeEventListener('mdict-open-saved', openSaved)
  }, [setSidebarOpen])

  const close = () => {
    setSidebarOpen(false)
    window.setTimeout(() => returnFocusRef.current?.focus(), 0)
  }

  const goToSource = (sourceId: string) => {
    window.dispatchEvent(new CustomEvent('mdict-source-navigate', { detail: { sourceId } }))
    if (!window.matchMedia('(min-width: 960px)').matches) close()
  }

  return (
    <>
      {sidebarOpen && <button className="drawer-scrim" aria-label="Close source navigation" onClick={close} />}
      <aside ref={asideRef} className={`source-ledger ${sidebarOpen ? 'is-open' : ''}`} aria-label="Dictionary workspace navigation">
        <header className="ledger-header">
          <div className="brand-lockup">
            <span className="brand-mark">M</span>
            <span>Mdict<span>Live</span></span>
          </div>
          <button className="icon-button ledger-close" aria-label="Close navigation" onClick={close}>
            <X size={18} />
          </button>
        </header>
        <div className="ledger-intro">
          <span className="eyebrow">Your library</span>
          <strong>{sources.length} source{sources.length === 1 ? '' : 's'}</strong>
          <small>{lookup?.mode === 'v2' ? 'Secure v2 evidence' : 'Legacy fallback mode'}</small>
        </div>
        <div className="ledger-tabs" role="tablist" aria-label="Library sections">
          {([
            ['sources', Library, 'Sources'],
            ['saved', BookMarked, 'Saved'],
            ['history', Clock3, 'History'],
          ] as const).map(([value, Icon, label]) => (
            <button
              key={value}
              role="tab"
              aria-selected={tab === value}
              className={tab === value ? 'is-active' : ''}
              onClick={() => setTab(value)}
            >
              <Icon size={15} /> {label}
            </button>
          ))}
        </div>
        <div className="ledger-content">
          {tab === 'sources' && (
            <div className="source-list" aria-busy={loading}>
              {sources.map((source) => {
                const matched = entrySourceIds.has(source.id)
                const failed = failedSourceIds.has(source.id) || !source.available
                return (
                  <button
                    key={source.id}
                    className={`source-item ${matched ? 'has-result' : ''}`}
                    onClick={() => goToSource(source.id)}
                    disabled={!matched}
                    title={matched ? `Go to ${source.title}` : `${source.title} has no result in this lookup`}
                  >
                    <span className="source-glyph">{source.title.slice(0, 1).toUpperCase()}</span>
                    <span className="source-copy">
                      <strong>{source.title}</strong>
                      <small>{failed ? source.unavailableReason ?? 'Unavailable' : matched ? 'Result available' : 'No current match'}</small>
                    </span>
                    <span className={`source-status ${failed ? 'is-failed' : matched ? 'is-ready' : ''}`} />
                  </button>
                )
              })}
              {!loading && sources.length === 0 && <p className="empty-ledger">No dictionary sources found.</p>}
            </div>
          )}
          {tab === 'history' && (
            <div>
              <button className="ledger-action" onClick={() => clearHistory.mutate()}>
                <Trash2 size={13} /> Clear history
              </button>
              <div className="ledger-word-list">
                {history.map((item) => (
                  <button key={item.word} onClick={() => { setSearchWord(item.word); close() }}>
                    <Clock3 size={14} /> <span>{item.word}</span>
                  </button>
                ))}
                {history.length === 0 && <p className="empty-ledger">No history yet.</p>}
              </div>
            </div>
          )}
          {tab === 'saved' && (
            <div>
              {wordbookId === null ? (
                <div className="ledger-word-list">
                  {wordbooks.map((wordbook) => (
                    <button key={wordbook.id} onClick={() => setWordbookId(wordbook.id)}>
                      <BookOpen size={14} /> <span>{wordbook.name}</span>
                    </button>
                  ))}
                  {wordbooks.length === 0 && <p className="empty-ledger">No saved word lists.</p>}
                </div>
              ) : (
                <>
                  <button className="ledger-action" onClick={() => setWordbookId(null)}>
                    <ChevronLeft size={14} /> All lists
                  </button>
                  <div className="ledger-word-list">
                    {entries.map((entry) => (
                      <div className="saved-row" key={entry.id}>
                        <button onClick={() => { setSearchWord(entry.word); close() }}>{entry.word}</button>
                        <button
                          aria-label={`Remove ${entry.word}`}
                          onClick={() => deleteEntry.mutate({ wbId: wordbookId, entryId: entry.id })}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                    {entries.length === 0 && <p className="empty-ledger">This list is empty.</p>}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
        <footer className="ledger-footer">Source order controls result order.</footer>
      </aside>
    </>
  )
}
