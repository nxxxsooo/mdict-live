import { describe, expect, it } from 'vitest'
import mdictLiveExtension, { tools } from '../extensions/mdict-live.js'

describe('Pi extension manifest', () => {
  it('registers exactly the four runtime-neutral read-only tools', () => {
    const registered: unknown[] = []
    mdictLiveExtension({ registerTool: (tool: unknown) => registered.push(tool) } as never)

    expect(registered).toHaveLength(4)
    expect(tools.map((tool) => tool.name)).toEqual([
      'mdict_sources',
      'mdict_lookup',
      'mdict_resolve',
      'mdict_suggest',
    ])
    expect(tools.every((tool) => !tool.name.includes('write'))).toBe(true)
  })
})
