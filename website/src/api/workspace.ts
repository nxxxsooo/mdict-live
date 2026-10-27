import { api, type HistoryItem, type WordMeta, type Wordbook, type WordbookEntry } from './dict'
import { rebaseSourceResources, servicePath } from './basePath'

const TOKEN_KEY = 'mdictLiveV2Token'

export type ApiMode = 'v2' | 'legacy'
export type RenderTrust = 'safe-v2' | 'legacy-inert'

export interface CitationReference {
  uri: string
  token: string
}

export interface WorkspaceSource {
  id: string
  revision?: string
  title: string
  enabled: boolean
  available: boolean
  order: number
  logo?: string
  unavailableReason?: string | null
  mode: ApiMode
  legacyType?: string
}

export interface WorkspaceTextBlock {
  blockId: string
  order: number
  text: string
  citation: CitationReference
}

export interface WorkspaceEntry {
  key: string
  sourceId: string
  revision?: string
  sourceTitle: string
  headword: string
  recordOrdinal: number
  html: string
  textBlocks: WorkspaceTextBlock[]
  citation?: CitationReference
  renderTrust: RenderTrust
  logo?: string
}

export interface WorkspaceSourceFailure {
  sourceId: string
  code: string
  message: string
}

export interface WorkspaceLookup {
  query: string
  normalizedQuery: string
  entries: WorkspaceEntry[]
  partial: boolean
  truncated: boolean
  truncationCauses: string[]
  failures: WorkspaceSourceFailure[]
  omittedSourceIds: string[]
  requestId?: string
  mode: ApiMode
}

export interface WorkspaceMetadata {
  available: boolean
  query: string
  dataset?: { id: string; title: string; version?: string | null }
  phonetic?: string
  definition?: string
  translation?: string
  tags: string[]
  mode: ApiMode
}

interface V2Envelope<T> {
  api_version: '2.0'
  request_id: string
  data: T
}

interface V2ErrorEnvelope {
  api_version: '2.0'
  request_id: string
  error: { code: string; message: string; details?: Record<string, unknown> }
}

interface V2Source {
  source_id: string
  revision: string
  title: string
  enabled: boolean
  order: number
  available: boolean
  unavailable_reason?: string | null
}

interface V2Entry {
  source_id: string
  revision: string
  entry_id: string
  headword: string
  record_ordinal: number
  citation: CitationReference
  html?: string
  text_blocks?: Array<{
    block_id: string
    order: number
    text: string
    citation: CitationReference
  }>
}

interface V2LookupData {
  query: string
  normalized_query: string
  entries: V2Entry[]
  partial: boolean
  truncated: boolean
  truncation?: { causes: string[]; resumable_source_ids?: string[] } | null
  progress: {
    failed_sources: Array<{ source_id: string; code: string; message: string }>
    omitted_source_ids: string[]
  }
}

export class WorkspaceApiError extends Error {
  status: number
  code: string
  requestId?: string

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message)
    this.name = 'WorkspaceApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

export function getV2Token(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setV2Token(token: string): void {
  try {
    const normalized = token.trim()
    if (normalized) sessionStorage.setItem(TOKEN_KEY, normalized)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage may be disabled; the legacy adapter remains available.
  }
  window.dispatchEvent(new CustomEvent('mdict-token-changed'))
}

async function fetchV2<T>(path: string, init?: RequestInit): Promise<V2Envelope<T>> {
  const token = getV2Token()
  if (!token) throw new WorkspaceApiError(0, 'token_missing', 'No v2 token is configured.')
  const response = await fetch(servicePath(path), {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const payload = (await response.json()) as V2Envelope<T> | V2ErrorEnvelope
  if (!response.ok || 'error' in payload) {
    const error = 'error' in payload ? payload.error : { code: 'http_error', message: 'Request failed.' }
    throw new WorkspaceApiError(response.status, error.code, error.message, payload.request_id)
  }
  return payload
}

function sourceMap(sources: WorkspaceSource[]): Map<string, WorkspaceSource> {
  return new Map(sources.map((source) => [source.id, source]))
}

async function getSources(): Promise<WorkspaceSource[]> {
  if (getV2Token()) {
    const response = await fetchV2<{ sources: V2Source[] }>('/api/v2/sources')
    return response.data.sources.map((source) => ({
      id: source.source_id,
      revision: source.revision,
      title: source.title,
      enabled: source.enabled,
      available: source.available,
      order: source.order,
      unavailableReason: source.unavailable_reason,
      mode: 'v2' as const,
    }))
  }
  const sources = await api.getDicts()
  return sources
    .filter((source) => source.type !== 'app')
    .map((source, order) => ({
      id: source.uuid,
      title: source.title,
      enabled: source.enabled,
      available: true,
      order,
      logo: source.logo,
      mode: 'legacy' as const,
      legacyType: source.type,
    }))
}

async function lookup(
  query: string,
  sources: WorkspaceSource[],
  selectedSourceId?: string,
): Promise<WorkspaceLookup> {
  if (getV2Token()) {
    const sourceIds = selectedSourceId && selectedSourceId !== 'all' ? [selectedSourceId] : undefined
    const response = await fetchV2<V2LookupData>('/api/v2/lookup', {
      method: 'POST',
      body: JSON.stringify({
        query,
        source_ids: sourceIds,
        representations: ['html', 'text'],
        record_history: true,
      }),
    })
    const bySource = sourceMap(sources)
    return {
      query: response.data.query,
      normalizedQuery: response.data.normalized_query,
      entries: response.data.entries.map((entry) => ({
        key: `${entry.source_id}:${entry.entry_id}`,
        sourceId: entry.source_id,
        revision: entry.revision,
        sourceTitle: bySource.get(entry.source_id)?.title ?? entry.source_id,
        headword: entry.headword,
        recordOrdinal: entry.record_ordinal,
        html: rebaseSourceResources(entry.html ?? '<p>Renderable HTML was not requested.</p>'),
        textBlocks: (entry.text_blocks ?? []).map((block) => ({
          blockId: block.block_id,
          order: block.order,
          text: block.text,
          citation: block.citation,
        })),
        citation: entry.citation,
        renderTrust: 'safe-v2' as const,
      })),
      partial: response.data.partial,
      truncated: response.data.truncated,
      truncationCauses: response.data.truncation?.causes ?? [],
      failures: response.data.progress.failed_sources.map((failure) => ({
        sourceId: failure.source_id,
        code: failure.code,
        message: failure.message,
      })),
      omittedSourceIds: response.data.progress.omitted_source_ids,
      requestId: response.request_id,
      mode: 'v2',
    }
  }

  const legacy =
    selectedSourceId && selectedSourceId !== 'all'
      ? await api.lookupWord(selectedSourceId, query).then((result) => ({
          word: result.word,
          results: result.found ? [result] : [],
          total: result.found ? 1 : 0,
        }))
      : await api.lookupAll(query)
  return {
    query: legacy.word,
    normalizedQuery: legacy.word.trim(),
    entries: legacy.results.map((entry, index) => ({
      key: `${entry.uuid}:${index}`,
      sourceId: entry.uuid,
      sourceTitle: entry.title ?? sources.find((source) => source.id === entry.uuid)?.title ?? 'Dictionary',
      headword: legacy.word,
      recordOrdinal: index,
      html: rebaseSourceResources(entry.html),
      textBlocks: [],
      renderTrust: 'legacy-inert' as const,
      logo: entry.logo,
    })),
    partial: false,
    truncated: false,
    truncationCauses: [],
    failures: [],
    omittedSourceIds: [],
    mode: 'legacy',
  }
}

async function suggestions(prefix: string): Promise<string[]> {
  if (getV2Token()) {
    const query = new URLSearchParams({ prefix, limit: '20' })
    const response = await fetchV2<{
      suggestions: Array<{ headword: string }>
    }>(`/api/v2/suggestions?${query}`)
    return response.data.suggestions.map((suggestion) => suggestion.headword)
  }
  return api.suggest(prefix)
}

async function metadata(query: string): Promise<WorkspaceMetadata> {
  if (getV2Token()) {
    const response = await fetchV2<{
      available: boolean
      query: string
      records: Array<{
        dataset: { id: string; title: string; version?: string | null }
        phonetic?: string
        definition?: string
        translation?: string
        tags?: string[]
      }>
    }>(`/api/v2/metadata?q=${encodeURIComponent(query)}`)
    const record = response.data.records[0]
    return {
      available: response.data.available,
      query: response.data.query,
      dataset: record?.dataset,
      phonetic: record?.phonetic,
      definition: record?.definition,
      translation: record?.translation,
      tags: record?.tags ?? [],
      mode: 'v2',
    }
  }
  const record: WordMeta = await api.getWordMeta(query)
  return {
    available: record.found,
    query,
    dataset: record.found ? { id: 'ecdict', title: 'ECDICT lexical metadata' } : undefined,
    phonetic: record.phonetic,
    definition: record.definition,
    translation: record.translation,
    tags: record.tags ?? [],
    mode: 'legacy',
  }
}

async function updateSource(sourceId: string, enabled: boolean): Promise<void> {
  if (getV2Token()) {
    await fetchV2(`/api/v2/sources/${encodeURIComponent(sourceId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
    return
  }
  await api.toggleDict(sourceId)
}

export const workspaceApi = {
  getSources,
  lookup,
  suggestions,
  metadata,
  updateSource,
  resolveCitation: (token: string) => fetchV2(`/api/v2/citations/${encodeURIComponent(token)}`),
  getHistory: (limit = 100): Promise<HistoryItem[]> => api.getHistory(limit),
  clearHistory: api.clearHistory,
  getWordbooks: (): Promise<Wordbook[]> => api.getWordbooks(),
  getWordbookEntries: (wordbookId: number): Promise<WordbookEntry[]> =>
    api.getWordbookEntries(wordbookId),
  createWordbook: api.createWordbook,
  deleteWordbook: api.deleteWordbook,
  addWordbookEntry: api.addWordbookEntry,
  deleteWordbookEntry: api.deleteWordbookEntry,
  checkWordInWordbooks: api.checkWordInWordbooks,
}
