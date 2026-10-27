import { createServer } from 'node:http'

const port = Number(process.env.MDICT_FIXTURE_PORT || 5259)
const token = process.env.MDICT_LIVE_TOKEN || 'private-test-token-0123456789abcdef'

function send(response, status, payload) {
  const body = JSON.stringify(payload)
  response.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body),
  })
  response.end(body)
}

const server = createServer((request, response) => {
  if (request.headers.authorization !== `Bearer ${token}`) {
    send(response, 401, {
      api_version: '2.0',
      request_id: 'req_auth',
      error: { code: 'authentication_required', message: 'Authentication failed.' },
    })
    return
  }
  const url = new URL(request.url || '/', `http://127.0.0.1:${port}`)
  if (url.pathname === '/api/v2') {
    send(response, 200, { api_version: '2.0', request_id: 'req_discovery', data: { api_version: '2.0' } })
    return
  }
  if (url.pathname === '/api/v2/sources') {
    send(response, 200, {
      api_version: '2.0',
      request_id: 'req_sources',
      data: { sources: [{
        source_id: 'src_fixture_oald',
        revision: 'rev_fixture_001',
        title: 'OALD fixture',
        enabled: true,
        available: true,
        order: 0,
      }] },
    })
    return
  }
  if (url.pathname === '/api/v2/lookup') {
    const query = url.searchParams.get('q') || ''
    send(response, 200, {
      api_version: '2.0',
      request_id: `req_lookup_${query}`,
      data: {
        query,
        normalized_query: query,
        entries: [{
          source_id: 'src_fixture_oald',
          revision: 'rev_fixture_001',
          entry_id: 'ent_right_fixture',
          headword: query,
          record_ordinal: 0,
          citation: {
            uri: 'mdict://src_fixture_oald/rev_fixture_001/rep-v1/ent_right_fixture',
            token: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          },
          html: '<script>must-not-reach-model()</script>',
          text_blocks: [{
            block_id: 'blk_definition',
            order: 0,
            text: 'True or correct as a fact; suitable for a particular purpose.',
            citation: {
              uri: 'mdict://src_fixture_oald/rev_fixture_001/rep-v1/ent_right_fixture#blk_definition',
              token: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
            },
          }],
        }],
        partial: false,
        truncated: false,
        truncation: null,
        progress: { failed_sources: [], omitted_source_ids: [] },
      },
    })
    return
  }
  send(response, 404, {
    api_version: '2.0',
    request_id: 'req_missing',
    error: { code: 'not_found', message: 'Not found.' },
  })
})

server.listen(port, '127.0.0.1', () => {
  process.stdout.write(`ready http://127.0.0.1:${port}\n`)
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)))
}
