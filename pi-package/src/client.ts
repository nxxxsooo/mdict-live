import { readFileSync, statSync } from 'node:fs'

export const AGENT_CONTRACT_VERSION = 'agent-tools-v1'
export const MAX_TOOL_RESULT_BYTES = 32 * 1024

export interface TransportConfig {
  baseUrl: string
  token: string
  timeoutMs: number
}

export interface AgentEnvelope<T> {
  contract_version: typeof AGENT_CONTRACT_VERSION
  request_id: string
  data: T
}

interface ApiEnvelope<T> {
  api_version: '2.0'
  request_id: string
  data: T
}

interface ApiErrorEnvelope {
  api_version?: string
  request_id?: string
  error?: { code?: string; message?: string }
}

interface Citation {
  uri: string
  token: string
}

interface ApiSource {
  source_id: string
  revision: string
  title: string
  enabled: boolean
  available: boolean
  order: number
  unavailable_reason?: string | null
}

interface ApiEntry {
  source_id: string
  revision: string
  entry_id: string
  headword: string
  record_ordinal: number
  citation: Citation
  html?: string
  text_blocks?: Array<{ block_id: string; order: number; text: string; citation: Citation }>
}

interface ApiLookupData {
  query: string
  normalized_query: string
  entries: ApiEntry[]
  partial: boolean
  truncated: boolean
  truncation?: { causes?: string[] } | null
  progress?: {
    failed_sources?: Array<{ source_id: string; code: string; message: string }>
    omitted_source_ids?: string[]
  }
}

export class MdictToolError extends Error {
  constructor(
    public readonly category: 'configuration' | 'authentication' | 'transport' | 'compatibility' | 'server',
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = 'MdictToolError'
  }
}

function normalizeBaseUrl(raw: string): string {
  let url: URL
  try {
    url = new URL(raw.trim())
  } catch {
    throw new MdictToolError('configuration', 'MdictLive URL must be an absolute HTTP URL.')
  }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password || url.search || url.hash) {
    throw new MdictToolError('configuration', 'MdictLive URL must be an absolute credential-free HTTP URL.')
  }
  return url.toString().replace(/\/$/, '')
}

function readProtectedToken(path: string): string {
  try {
    const metadata = statSync(path)
    if (!metadata.isFile()) throw new Error('not-file')
    if (process.platform !== 'win32' && (metadata.mode & 0o077) !== 0) {
      throw new MdictToolError('configuration', 'MdictLive token file permissions are too broad; use mode 0600.')
    }
    const value = readFileSync(path, 'utf8').trim()
    if (!value) throw new Error('empty')
    return value
  } catch (error) {
    if (error instanceof MdictToolError) throw error
    throw new MdictToolError('configuration', 'MdictLive token file cannot be read.')
  }
}

export function loadTransportConfig(env: NodeJS.ProcessEnv = process.env): TransportConfig {
  const baseUrl = normalizeBaseUrl(env.MDICT_LIVE_URL ?? 'http://127.0.0.1:5248')
  const token = env.MDICT_LIVE_TOKEN?.trim() || (env.MDICT_LIVE_TOKEN_FILE ? readProtectedToken(env.MDICT_LIVE_TOKEN_FILE) : '')
  if (!token) {
    throw new MdictToolError('configuration', 'MdictLive bearer token is not configured.')
  }
  const timeoutSeconds = Number(env.MDICT_LIVE_TIMEOUT ?? '10')
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 3600) {
    throw new MdictToolError('configuration', 'MdictLive timeout must be between 0 and 3600 seconds.')
  }
  return { baseUrl, token, timeoutMs: Math.round(timeoutSeconds * 1000) }
}

function byteLength(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value), 'utf8')
}

function boundLookup<T extends { data: { entries: Array<{ text_blocks: Array<{ text: string }> }>; truncated: boolean; truncation_causes: string[] } }>(
  result: T,
): T {
  while (byteLength(result) > MAX_TOOL_RESULT_BYTES) {
    const blocks = result.data.entries.flatMap((entry) => entry.text_blocks)
    const longest = blocks.sort((left, right) => right.text.length - left.text.length)[0]
    if (longest && longest.text.length > 256) {
      longest.text = `${longest.text.slice(0, Math.max(128, Math.floor(longest.text.length * 0.65)))}…`
    } else {
      const entry = [...result.data.entries].reverse().find((candidate) => candidate.text_blocks.length > 1)
      if (entry) entry.text_blocks.pop()
      else if (result.data.entries.length > 1) result.data.entries.pop()
      else break
    }
    result.data.truncated = true
    if (!result.data.truncation_causes.includes('agent_output_bytes')) {
      result.data.truncation_causes.push('agent_output_bytes')
    }
  }
  return result
}

function bounded<T>(result: AgentEnvelope<T>): AgentEnvelope<T> {
  if (byteLength(result) <= MAX_TOOL_RESULT_BYTES) return result
  const copy = structuredClone(result) as AgentEnvelope<T> & {
    data: { entries?: Array<{ text_blocks: Array<{ text: string }> }>; truncated?: boolean; truncation_causes?: string[] }
  }
  if (Array.isArray(copy.data.entries)) {
    copy.data.truncated = true
    copy.data.truncation_causes ??= []
    return boundLookup(copy as never) as AgentEnvelope<T>
  }
  throw new MdictToolError('server', 'MdictLive tool result exceeded its safe output bound.', result.request_id)
}

export class MdictClient {
  private compatible = false

  constructor(
    private readonly config: TransportConfig,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  private async request<T>(path: string, signal?: AbortSignal): Promise<ApiEnvelope<T>> {
    const controller = new AbortController()
    const abort = () => controller.abort()
    signal?.addEventListener('abort', abort, { once: true })
    const timer = setTimeout(abort, this.config.timeoutMs)
    try {
      const response = await this.fetchImpl(`${this.config.baseUrl}${path}`, {
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${this.config.token}`,
          'User-Agent': 'mdict-live-pi/1',
        },
        signal: controller.signal,
      })
      let payload: ApiEnvelope<T> | ApiErrorEnvelope
      try {
        payload = await response.json() as ApiEnvelope<T> | ApiErrorEnvelope
      } catch {
        throw new MdictToolError('compatibility', 'MdictLive returned an incompatible non-JSON response.')
      }
      const requestId = typeof payload.request_id === 'string' ? payload.request_id : undefined
      if (!response.ok || 'error' in payload) {
        if (response.status === 401 || response.status === 403) {
          throw new MdictToolError('authentication', 'MdictLive authentication failed.', requestId)
        }
        const code = 'error' in payload && payload.error?.code ? payload.error.code : `http_${response.status}`
        throw new MdictToolError('server', `MdictLive request failed (${code}).`, requestId)
      }
      if (payload.api_version !== '2.0' || !requestId || !('data' in payload)) {
        throw new MdictToolError('compatibility', 'MdictLive response is not a compatible v2 envelope.', requestId)
      }
      return payload
    } catch (error) {
      if (error instanceof MdictToolError) throw error
      throw new MdictToolError('transport', 'MdictLive transport failed.')
    } finally {
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
    }
  }

  private async ensureCompatible(signal?: AbortSignal): Promise<void> {
    if (this.compatible) return
    const response = await this.request<{ api_version: string }>('/api/v2', signal)
    if (response.data.api_version !== '2.0') {
      throw new MdictToolError('compatibility', 'MdictLive discovery reports an incompatible API.', response.request_id)
    }
    this.compatible = true
  }

  async sources(signal?: AbortSignal) {
    await this.ensureCompatible(signal)
    const response = await this.request<{ sources: ApiSource[] }>('/api/v2/sources', signal)
    return bounded({
      contract_version: AGENT_CONTRACT_VERSION,
      request_id: response.request_id,
      data: { sources: response.data.sources.slice(0, 256) },
    })
  }

  async lookup(query: string, sourceIds: string[] = [], signal?: AbortSignal) {
    await this.ensureCompatible(signal)
    const params = new URLSearchParams({ q: query, representation: 'text' })
    for (const sourceId of sourceIds) params.append('source_id', sourceId)
    const response = await this.request<ApiLookupData>(`/api/v2/lookup?${params}`, signal)
    return bounded({
      contract_version: AGENT_CONTRACT_VERSION,
      request_id: response.request_id,
      data: {
        query: response.data.query,
        normalized_query: response.data.normalized_query,
        entries: response.data.entries.map(({ html: _html, text_blocks = [], ...entry }) => ({ ...entry, text_blocks })),
        partial: response.data.partial,
        truncated: response.data.truncated,
        truncation_causes: response.data.truncation?.causes ?? [],
        failed_sources: response.data.progress?.failed_sources ?? [],
        omitted_source_ids: response.data.progress?.omitted_source_ids ?? [],
      },
    })
  }

  async resolve(citationToken: string, signal?: AbortSignal) {
    await this.ensureCompatible(signal)
    const response = await this.request<Record<string, unknown>>(`/api/v2/citations/${encodeURIComponent(citationToken)}`, signal)
    return bounded({ contract_version: AGENT_CONTRACT_VERSION, request_id: response.request_id, data: response.data })
  }

  async suggest(prefix: string, sourceIds: string[] = [], fuzzy = false, limit = 20, signal?: AbortSignal) {
    await this.ensureCompatible(signal)
    const params = new URLSearchParams({ prefix, fuzzy: String(fuzzy), limit: String(limit) })
    for (const sourceId of sourceIds) params.append('source_id', sourceId)
    const response = await this.request<Record<string, unknown>>(`/api/v2/suggestions?${params}`, signal)
    return bounded({ contract_version: AGENT_CONTRACT_VERSION, request_id: response.request_id, data: response.data })
  }
}

export function safeToolError(error: unknown): AgentEnvelope<{ error: { category: string; message: string } }> {
  const known = error instanceof MdictToolError
    ? error
    : new MdictToolError('transport', 'MdictLive tool failed.')
  return {
    contract_version: AGENT_CONTRACT_VERSION,
    request_id: known.requestId ?? 'unavailable',
    data: { error: { category: known.category, message: known.message } },
  }
}
