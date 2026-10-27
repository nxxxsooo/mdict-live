import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkspaceApiError, setV2Token, workspaceApi } from './workspace'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('workspaceApi', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  afterEach(() => {
    sessionStorage.clear()
  })

  it('maps v2 sources, lookup entries, citations, truncation, and partial failures', async () => {
    setV2Token('private-test-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          api_version: '2.0',
          request_id: 'req-sources',
          data: {
            sources: [
              {
                source_id: 'src_oald',
                revision: 'rev_001',
                title: 'OALD 10',
                enabled: true,
                order: 2,
                available: true,
              },
            ],
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          api_version: '2.0',
          request_id: 'req-lookup',
          data: {
            query: 'right',
            normalized_query: 'right',
            entries: [
              {
                source_id: 'src_oald',
                revision: 'rev_001',
                entry_id: 'entry_1',
                headword: 'right',
                record_ordinal: 0,
                citation: { uri: 'mdict://src_oald/right/0', token: 'entry-token' },
                html: '<article><b>Correct.</b></article>',
                text_blocks: [
                  {
                    block_id: 'block_1',
                    order: 0,
                    text: 'Correct.',
                    citation: { uri: 'mdict://src_oald/right/0#block_1', token: 'block-token' },
                  },
                ],
              },
            ],
            partial: true,
            truncated: true,
            truncation: { causes: ['entry_limit'], resumable_source_ids: ['src_oald'] },
            progress: {
              failed_sources: [{ source_id: 'src_slow', code: 'timeout', message: 'Timed out.' }],
              omitted_source_ids: ['src_slow'],
            },
          },
        }),
      )

    const sources = await workspaceApi.getSources()
    const result = await workspaceApi.lookup('right', sources)

    expect(sources).toEqual([
      expect.objectContaining({ id: 'src_oald', revision: 'rev_001', mode: 'v2', order: 2 }),
    ])
    expect(result).toMatchObject({
      requestId: 'req-lookup',
      mode: 'v2',
      partial: true,
      truncated: true,
      truncationCauses: ['entry_limit'],
      omittedSourceIds: ['src_slow'],
    })
    expect(result.entries[0]).toMatchObject({
      key: 'src_oald:entry_1',
      sourceTitle: 'OALD 10',
      renderTrust: 'safe-v2',
      citation: { token: 'entry-token' },
      textBlocks: [{ text: 'Correct.', citation: { token: 'block-token' } }],
    })
    expect(result.failures).toEqual([
      { sourceId: 'src_slow', code: 'timeout', message: 'Timed out.' },
    ])
    expect(fetchMock.mock.calls[1][1]).toMatchObject({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer private-test-token' }),
    })
  })

  it('uses the explicit inert legacy fallback only when no v2 token exists', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse([
          { uuid: 'legacy-oald', title: 'Legacy OALD', logo: '', type: 'mdx', enabled: true },
          { uuid: 'app-source', title: 'App', logo: '', type: 'app', enabled: true },
        ]),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          word: 'right',
          results: [
            {
              word: 'right',
              uuid: 'legacy-oald',
              title: 'Legacy OALD',
              found: true,
              html: '<script>unsafe()</script><p>Correct.</p>',
            },
          ],
          total: 1,
        }),
      )

    const sources = await workspaceApi.getSources()
    const result = await workspaceApi.lookup('right', sources)

    expect(sources).toHaveLength(1)
    expect(sources[0]).toMatchObject({ id: 'legacy-oald', mode: 'legacy' })
    expect(result.mode).toBe('legacy')
    expect(result.entries[0].renderTrust).toBe('legacy-inert')
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/dicts', undefined)
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/lookup/right', undefined)
  })

  it('does not silently downgrade an invalid v2 token to legacy routes', async () => {
    setV2Token('invalid-token')
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(
        {
          api_version: '2.0',
          request_id: 'req-denied',
          error: { code: 'unauthorized', message: 'Invalid bearer token.' },
        },
        401,
      ),
    )

    await expect(workspaceApi.getSources()).rejects.toEqual(
      expect.objectContaining<Partial<WorkspaceApiError>>({
        status: 401,
        code: 'unauthorized',
        requestId: 'req-denied',
      }),
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v2/sources',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer invalid-token' }),
      }),
    )
  })
})
