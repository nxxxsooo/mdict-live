import { Type } from '@earendil-works/pi-ai'
import { defineTool, type ExtensionAPI } from '@earendil-works/pi-coding-agent'
import { loadTransportConfig, MdictClient, safeToolError } from '../src/client.js'

function client(): MdictClient {
  return new MdictClient(loadTransportConfig())
}

function result(value: unknown) {
  return {
    content: [{ type: 'text' as const, text: JSON.stringify(value) }],
    details: {},
  }
}

async function executeSafely(operation: () => Promise<unknown>) {
  try {
    return result(await operation())
  } catch (error) {
    return result(safeToolError(error))
  }
}

const sourceId = Type.String({
  minLength: 1,
  maxLength: 160,
  pattern: '^[A-Za-z0-9_-]+$',
  description: 'Stable source_id returned by mdict_sources',
})

const sourcesTool = defineTool({
  name: 'mdict_sources',
  label: 'Dictionary Sources',
  description: 'List ordered MdictLive dictionary sources and availability without exposing storage paths.',
  promptSnippet: 'List available private dictionary sources',
  parameters: Type.Object({}, { additionalProperties: false }),
  async execute(_toolCallId, _params, signal) {
    return executeSafely(() => client().sources(signal))
  },
})

const lookupTool = defineTool({
  name: 'mdict_lookup',
  label: 'Dictionary Lookup',
  description: 'Look up an exact word or phrase and return bounded text evidence with stable citations, never raw HTML.',
  promptSnippet: 'Retrieve exact source-cited dictionary evidence',
  promptGuidelines: [
    'Use mdict_lookup for lexical claims; distinguish retrieved evidence from your inference and cite the returned mdict:// URIs.',
  ],
  parameters: Type.Object({
    query: Type.String({ minLength: 1, maxLength: 256, description: 'Exact word or phrase to look up' }),
    source_ids: Type.Optional(Type.Array(sourceId, { maxItems: 32, uniqueItems: true })),
  }, { additionalProperties: false }),
  async execute(_toolCallId, params, signal) {
    return executeSafely(() => client().lookup(params.query, params.source_ids ?? [], signal))
  },
})

const resolveTool = defineTool({
  name: 'mdict_resolve',
  label: 'Resolve Citation',
  description: 'Resolve one protected MdictLive citation token to current source and optional text-block evidence.',
  promptSnippet: 'Resolve a protected dictionary citation token',
  parameters: Type.Object({
    citation_token: Type.String({ minLength: 32, maxLength: 4096, pattern: '^[A-Za-z0-9_-]+$' }),
  }, { additionalProperties: false }),
  async execute(_toolCallId, params, signal) {
    return executeSafely(() => client().resolve(params.citation_token, signal))
  },
})

const suggestTool = defineTool({
  name: 'mdict_suggest',
  label: 'Dictionary Suggestions',
  description: 'Return deterministic bounded headword suggestions; fuzzy fallback runs only when explicitly requested.',
  promptSnippet: 'Suggest dictionary headwords without searching definition bodies',
  parameters: Type.Object({
    prefix: Type.String({ minLength: 1, maxLength: 256 }),
    source_ids: Type.Optional(Type.Array(sourceId, { maxItems: 32, uniqueItems: true })),
    fuzzy: Type.Optional(Type.Boolean({ default: false })),
    limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100, default: 20 })),
  }, { additionalProperties: false }),
  async execute(_toolCallId, params, signal) {
    return executeSafely(() => client().suggest(
      params.prefix,
      params.source_ids ?? [],
      params.fuzzy ?? false,
      params.limit ?? 20,
      signal,
    ))
  },
})

export const tools = [sourcesTool, lookupTool, resolveTool, suggestTool]

export default function mdictLiveExtension(pi: ExtensionAPI) {
  for (const tool of tools) pi.registerTool(tool)
}
