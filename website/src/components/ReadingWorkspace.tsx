import { useEffect, useMemo, useRef } from 'react'
import { AlertCircle, Bookmark, Check, Copy, FileSearch, LoaderCircle, Sparkles } from 'lucide-react'
import type { WorkspaceLookup, WorkspaceSource } from '@/api/workspace'
import { useWorkspaceMetadata } from '@/hooks/useWorkspace'
import {
  useAddWordbookEntry,
  useCheckWordInWordbooks,
  useCreateWordbook,
  useDeleteWordbookEntry,
  useWordbooks,
} from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'
import { LegacyEntryFrame, NativeEntryFrame } from './NativeEntryFrame'

interface ReadingWorkspaceProps {
  query: string
  sources: WorkspaceSource[]
  lookup?: WorkspaceLookup
  loading: boolean
  error: Error | null
  onRefresh: () => void
}

function SaveWordButton({ word }: { word: string }) {
  const { data: memberships = [] } = useCheckWordInWordbooks(word)
  const { data: wordbooks = [] } = useWordbooks()
  const createWordbook = useCreateWordbook()
  const addEntry = useAddWordbookEntry()
  const deleteEntry = useDeleteWordbookEntry()
  const saved = memberships.length > 0

  const toggle = async () => {
    if (saved) {
      memberships.forEach((entry) =>
        deleteEntry.mutate({ wbId: entry.wordbook_id, entryId: entry.id }),
      )
      return
    }
    const wordbookId = wordbooks[0]?.id ?? (await createWordbook.mutateAsync('My Words')).id
    addEntry.mutate({ wbId: wordbookId, word })
  }

  return (
    <button className={`secondary-button ${saved ? 'is-saved' : ''}`} onClick={() => void toggle()}>
      {saved ? <Check size={15} /> : <Bookmark size={15} />}
      {saved ? 'Saved' : 'Save word'}
    </button>
  )
}

function CitationButton({ uri }: { uri: string }) {
  const copy = () => void navigator.clipboard?.writeText(uri)
  return (
    <button className="citation-button" onClick={copy} title={uri}>
      <Copy size={13} /> Cite
    </button>
  )
}

export function ReadingWorkspace({ query, sources, lookup, loading, error, onRefresh }: ReadingWorkspaceProps) {
  const setSearchWord = useAppStore((state) => state.setSearchWord)
  const sourceRefs = useRef(new Map<string, HTMLElement>())
  const { data: metadata } = useWorkspaceMetadata(query)
  const sourcesById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources])

  useEffect(() => {
    const navigate = (event: Event) => {
      const sourceId = (event as CustomEvent).detail?.sourceId
      if (typeof sourceId === 'string') {
        sourceRefs.current.get(sourceId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
    window.addEventListener('mdict-source-navigate', navigate)
    return () => window.removeEventListener('mdict-source-navigate', navigate)
  }, [])

  const quickBlock = lookup?.entries
    .flatMap((entry) => entry.textBlocks.map((block) => ({ entry, block })))
    .find(({ block }) => block.text.trim().toLocaleLowerCase() !== lookup.normalizedQuery.toLocaleLowerCase() && block.text.length > 5)
  const quickSense = quickBlock?.block.text ?? metadata?.definition
  const quickTranslation = metadata?.translation

  if (!query) {
    return (
      <section className="workspace-state initial-state">
        <span className="state-icon"><FileSearch size={28} /></span>
        <span className="eyebrow">Private reference workspace</span>
        <h1>Look up a word or phrase</h1>
        <p>Source-faithful entries, stable citations, and optional agent guidance stay clearly separated.</p>
      </section>
    )
  }

  return (
    <section className="reading-sheet" aria-busy={loading} aria-live="polite">
      <header className="entry-overview">
        <div>
          <span className="eyebrow">Dictionary lookup</span>
          <h1>{lookup?.normalizedQuery ?? query}</h1>
          <div className="entry-meta-line">
            {metadata?.phonetic && <span>/{metadata.phonetic}/</span>}
            {metadata?.dataset && <span>{metadata.dataset.title}</span>}
            {lookup && <span>{lookup.entries.length} source entr{lookup.entries.length === 1 ? 'y' : 'ies'}</span>}
          </div>
        </div>
        <SaveWordButton word={lookup?.normalizedQuery ?? query} />
      </header>

      {quickSense && (
        <section className="quick-sense" aria-label="Quick sense">
          <div className="quick-sense-label">
            <span>A quick sense</span>
            <small>
              {quickBlock
                ? `First source sense · ${quickBlock.entry.sourceTitle}`
                : `${metadata?.dataset?.title ?? 'Structured metadata'} · deterministic`}
            </small>
          </div>
          <div className="quick-sense-copy">
            <p>{quickSense}</p>
            {quickTranslation && <span lang="zh">{quickTranslation}</span>}
            {quickBlock?.block.citation && <CitationButton uri={quickBlock.block.citation.uri} />}
          </div>
        </section>
      )}

      {loading && (
        <div className="workspace-state loading-state" role="status">
          <LoaderCircle className="spin" size={22} />
          <div><strong>Reading enabled sources</strong><span>The active query stays visible while results load.</span></div>
        </div>
      )}

      {error && !loading && (
        <div className="workspace-state error-state" role="alert">
          <AlertCircle size={22} />
          <div><strong>Lookup unavailable</strong><span>{error.message || 'No source completed the request.'}</span></div>
          <button className="secondary-button" onClick={onRefresh}>Try again</button>
        </div>
      )}

      {lookup?.partial && (
        <div className="partial-banner" role="status">
          <AlertCircle size={17} />
          <div>
            <strong>Partial evidence</strong>
            <span>{lookup.failures.map((failure) => `${sourcesById.get(failure.sourceId)?.title ?? failure.sourceId}: ${failure.code}`).join(' · ')}</span>
          </div>
        </div>
      )}

      {lookup?.truncated && (
        <div className="partial-banner is-bounded" role="status">
          <Sparkles size={17} />
          <div><strong>Bounded response</strong><span>{lookup.truncationCauses.join(' · ')}</span></div>
        </div>
      )}

      {lookup && !loading && !error && lookup.entries.length === 0 && (
        <div className="workspace-state no-match-state">
          <FileSearch size={24} />
          <div><strong>No dictionary match</strong><span>All completed sources returned no entry for “{lookup.normalizedQuery}”.</span></div>
        </div>
      )}

      <div className="source-document-list">
        {lookup?.entries.map((entry) => (
          <article
            key={entry.key}
            id={`source-${entry.sourceId}`}
            ref={(element) => {
              if (element) sourceRefs.current.set(entry.sourceId, element)
              else sourceRefs.current.delete(entry.sourceId)
            }}
            className="source-document"
          >
            <header className="source-document-header">
              <div className="source-identity">
                <span className="source-glyph large">{entry.sourceTitle.slice(0, 1).toUpperCase()}</span>
                <div>
                  <h2>{entry.sourceTitle}</h2>
                  <span>{entry.renderTrust === 'safe-v2' ? 'Native source · safe v2 representation' : 'Legacy inert fallback'}</span>
                </div>
              </div>
              <div className="source-actions">
                {entry.citation && <CitationButton uri={entry.citation.uri} />}
                {entry.revision && <code title={entry.revision}>{entry.revision.slice(0, 14)}</code>}
              </div>
            </header>
            {entry.renderTrust === 'safe-v2' ? (
              <NativeEntryFrame entry={entry} onEntry={setSearchWord} onRefresh={onRefresh} />
            ) : (
              <LegacyEntryFrame entry={entry} />
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
