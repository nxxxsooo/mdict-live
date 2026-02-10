// API types
export interface DictInfo {
  uuid: string
  title: string
  logo: string
  type: string
  enabled: boolean
}

export interface LookupResult {
  word: string
  uuid: string
  title?: string
  logo?: string
  found: boolean
  html: string
}

export interface LookupAllResult {
  word: string
  results: LookupResult[]
  total: number
}

export interface HistoryItem {
  word: string
  count: number
  last_time: string
}

export interface WordMeta {
  word: string
  found: boolean
  phonetic?: string
  definition?: string
  translation?: string
  oxford?: boolean
  collins?: number
  tags?: string[]
  bnc?: number
  frq?: number
  exchanges?: Record<string, string>
}

export interface Wordbook {
  id: number
  name: string
  created_at: string
}

export interface WordbookEntry {
  id: number
  wordbook_id: number
  word: string
  created_at: string
}

// API fetch helpers
const BASE = ''

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  getDicts: () => fetchJson<DictInfo[]>('/api/dicts'),

  lookupWord: (uuid: string, word: string) =>
    fetchJson<LookupResult>(`/api/dicts/${uuid}/lookup/${encodeURIComponent(word)}`),

  lookupAll: (word: string) =>
    fetchJson<LookupAllResult>(`/api/lookup/${encodeURIComponent(word)}`),

  suggest: (query: string, limit = 20) =>
    fetchJson<string[]>(`/api/suggest/${encodeURIComponent(query)}?limit=${limit}`),

  getHistory: (limit = 100) =>
    fetchJson<HistoryItem[]>(`/api/history?limit=${limit}`),

  clearHistory: () =>
    fetchJson<{ ok: boolean }>('/api/history/clear', { method: 'POST' }),

  getWordMeta: (word: string) =>
    fetchJson<WordMeta>(`/api/meta/${encodeURIComponent(word)}`),

  toggleDict: (uuid: string) =>
    fetchJson<{ uuid: string; enabled: boolean }>(`/api/dicts/${uuid}/toggle`, { method: 'POST' }),

  getWordbooks: () => fetchJson<Wordbook[]>('/api/wordbooks'),

  createWordbook: (name: string) =>
    fetchJson<Wordbook>('/api/wordbooks', {
      method: 'POST',
      body: JSON.stringify({ name }),
      headers: { 'Content-Type': 'application/json' },
    }),

  deleteWordbook: (id: number) =>
    fetchJson<{ ok: boolean }>(`/api/wordbooks/${id}`, { method: 'DELETE' }),

  updateWordbook: (id: number, name: string) =>
    fetchJson<{ ok: boolean }>(`/api/wordbooks/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ name }),
      headers: { 'Content-Type': 'application/json' },
    }),

  getWordbookEntries: (wbId: number) =>
    fetchJson<WordbookEntry[]>(`/api/wordbooks/${wbId}/entries`),

  addWordbookEntry: (wbId: number, word: string) =>
    fetchJson<WordbookEntry>(`/api/wordbooks/${wbId}/entries`, {
      method: 'POST',
      body: JSON.stringify({ word }),
      headers: { 'Content-Type': 'application/json' },
    }),

  deleteWordbookEntry: (wbId: number, entryId: number) =>
    fetchJson<{ ok: boolean }>(`/api/wordbooks/${wbId}/entries/${entryId}`, {
      method: 'DELETE',
    }),

  checkWordInWordbooks: (word: string) =>
    fetchJson<number[]>(`/api/wordbooks/entries?word=${encodeURIComponent(word)}`),
}
