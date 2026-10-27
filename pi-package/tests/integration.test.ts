import { createServer } from 'node:http'
import { afterEach, describe, expect, it } from 'vitest'
import { tools } from '../extensions/mdict-live.js'

const TOKEN = 'private-test-token-0123456789abcdef'

describe('Pi tool against a fake v2 service', () => {
  const originalEnvironment = { ...process.env }

  afterEach(() => {
    process.env = { ...originalEnvironment }
  })

  it('executes mdict_lookup through HTTP and returns only cited text evidence', async () => {
    const requests: Array<{ path: string; authorization?: string }> = []
    const server = createServer((request, response) => {
      requests.push({ path: request.url ?? '', authorization: request.headers.authorization })
      const payload = request.url === '/api/v2'
        ? { api_version: '2.0', request_id: 'req_discovery', data: { api_version: '2.0' } }
        : {
            api_version: '2.0',
            request_id: 'req_lookup',
            data: {
              query: 'right',
              normalized_query: 'right',
              entries: [{
                source_id: 'src_oald',
                revision: 'rev_1',
                entry_id: 'ent_1',
                headword: 'right',
                record_ordinal: 0,
                citation: { uri: 'mdict://src_oald/rev_1/rep-v1/ent_1', token: 'a'.repeat(40) },
                html: '<script>dictionaryCode()</script>',
                text_blocks: [{
                  block_id: 'blk_1',
                  order: 0,
                  text: 'True or correct as a fact.',
                  citation: { uri: 'mdict://src_oald/rev_1/rep-v1/ent_1#blk_1', token: 'b'.repeat(40) },
                }],
              }],
              partial: false,
              truncated: false,
              truncation: null,
              progress: { failed_sources: [], omitted_source_ids: [] },
            },
          }
      const body = JSON.stringify(payload)
      response.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) })
      response.end(body)
    })
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    try {
      const address = server.address()
      if (!address || typeof address === 'string') throw new Error('fixture server did not bind')
      process.env.MDICT_LIVE_URL = `http://127.0.0.1:${address.port}`
      process.env.MDICT_LIVE_TOKEN = TOKEN
      const lookup = tools.find((tool) => tool.name === 'mdict_lookup')
      if (!lookup) throw new Error('mdict_lookup was not registered')

      const toolResult = await lookup.execute(
        'call_fixture',
        { query: 'right' },
        new AbortController().signal,
        undefined,
        {} as never,
      )
      const text = toolResult.content[0]?.type === 'text' ? toolResult.content[0].text : ''

      expect(text).toContain('True or correct as a fact.')
      expect(text).toContain('mdict://src_oald')
      expect(text).not.toContain('dictionaryCode')
      expect(text).not.toContain(TOKEN)
      expect(requests).toHaveLength(2)
      expect(requests.every((request) => request.authorization === `Bearer ${TOKEN}`)).toBe(true)
    } finally {
      await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()))
    }
  })
})
