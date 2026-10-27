import { chmodSync, unlinkSync, writeFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  AGENT_CONTRACT_VERSION,
  MAX_TOOL_RESULT_BYTES,
  MdictClient,
  loadTransportConfig,
  safeToolError,
} from '../src/client.js'

const TOKEN = 'private-test-token-0123456789abcdef'

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function envelope(requestId: string, data: unknown) {
  return { api_version: '2.0', request_id: requestId, data }
}

describe('MdictClient', () => {
  afterEach(() => vi.restoreAllMocks())

  it('returns bounded cited text while excluding raw HTML and transport secrets', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(response(envelope('req_discovery', { api_version: '2.0' })))
      .mockResolvedValueOnce(response(envelope('req_lookup', {
        query: 'right',
        normalized_query: 'right',
        entries: [{
          source_id: 'src_oald',
          revision: 'rev_1',
          entry_id: 'ent_1',
          headword: 'right',
          record_ordinal: 0,
          citation: { uri: 'mdict://src_oald/rev_1/rep-v1/ent_1', token: 'a'.repeat(40) },
          html: '<script>shouldNeverReachTheModel()</script>',
          text_blocks: [{
            block_id: 'blk_1',
            order: 0,
            text: `True or correct as a fact.${' evidence'.repeat(8_000)}`,
            citation: { uri: 'mdict://src_oald/rev_1/rep-v1/ent_1#blk_1', token: 'b'.repeat(40) },
          }],
        }],
        partial: true,
        truncated: false,
        truncation: null,
        progress: {
          failed_sources: [{ source_id: 'src_slow', code: 'timeout', message: 'Timed out.' }],
          omitted_source_ids: ['src_slow'],
        },
      })))
    const client = new MdictClient(
      { baseUrl: 'https://dictionary.internal/private', token: TOKEN, timeoutMs: 1_000 },
      fetchMock,
    )

    const result = await client.lookup('right')
    const serialized = JSON.stringify(result)

    expect(result.contract_version).toBe(AGENT_CONTRACT_VERSION)
    expect(result.request_id).toBe('req_lookup')
    expect(result.data.partial).toBe(true)
    expect(result.data.truncated).toBe(true)
    expect(result.data.truncation_causes).toContain('agent_output_bytes')
    expect(result.data.entries[0].text_blocks[0].citation.uri).toMatch(/^mdict:\/\//)
    expect(Buffer.byteLength(serialized, 'utf8')).toBeLessThanOrEqual(MAX_TOOL_RESULT_BYTES)
    expect(serialized).not.toContain('shouldNeverReachTheModel')
    expect(serialized).not.toContain(TOKEN)
    expect(serialized).not.toContain('dictionary.internal')
    expect(fetchMock.mock.calls[1][0]).toContain('/private/api/v2/lookup?')
    expect((fetchMock.mock.calls[1][1]?.headers as Record<string, string>).Authorization).toBe(`Bearer ${TOKEN}`)
  })

  it('keeps authentication and server failures generic and request-correlated', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({
      api_version: '2.0',
      request_id: 'req_denied',
      error: { code: 'authentication_required', message: `private ${TOKEN}` },
    }, 401))
    const client = new MdictClient(
      { baseUrl: 'https://dictionary.internal', token: TOKEN, timeoutMs: 1_000 },
      fetchMock,
    )

    const error = await client.sources().catch((caught) => safeToolError(caught))
    const serialized = JSON.stringify(error)

    expect(serialized).toContain('req_denied')
    expect(serialized).toContain('authentication')
    expect(serialized).not.toContain(TOKEN)
    expect(serialized).not.toContain('dictionary.internal')
  })

  it('loads transport from a protected token file without returning it in config errors', () => {
    const tokenPath = `${process.env.TMPDIR ?? '/tmp'}/mdict-live-pi-token-${process.pid}`
    writeFileSync(tokenPath, TOKEN, 'utf8')
    chmodSync(tokenPath, 0o600)
    try {
      const config = loadTransportConfig({
        MDICT_LIVE_URL: 'http://127.0.0.1:5248/private',
        MDICT_LIVE_TOKEN_FILE: tokenPath,
        MDICT_LIVE_TIMEOUT: '2.5',
      })

      expect(config).toEqual({
        baseUrl: 'http://127.0.0.1:5248/private',
        token: TOKEN,
        timeoutMs: 2_500,
      })
    } finally {
      unlinkSync(tokenPath)
    }
  })

  it('maps source, citation, and suggestion calls to read-only v2 GET routes', async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(response(envelope('req_discovery', { api_version: '2.0' })))
      .mockResolvedValueOnce(response(envelope('req_sources', { sources: [] })))
      .mockResolvedValueOnce(response(envelope('req_resolve', { headword: 'right' })))
      .mockResolvedValueOnce(response(envelope('req_suggest', { prefix: 'rig', suggestions: [], fuzzy: true, truncated: false })))
    const client = new MdictClient(
      { baseUrl: 'http://127.0.0.1:5248', token: TOKEN, timeoutMs: 1_000 },
      fetchMock,
    )

    await client.sources()
    await client.resolve('a'.repeat(40))
    await client.suggest('rig', ['src_oald'], true, 8)

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init?.method ?? 'GET'])).toEqual([
      ['http://127.0.0.1:5248/api/v2', 'GET'],
      ['http://127.0.0.1:5248/api/v2/sources', 'GET'],
      [`http://127.0.0.1:5248/api/v2/citations/${'a'.repeat(40)}`, 'GET'],
      ['http://127.0.0.1:5248/api/v2/suggestions?prefix=rig&fuzzy=true&limit=8&source_id=src_oald', 'GET'],
    ])
  })
})
