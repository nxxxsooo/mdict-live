import { describe, expect, it } from 'vitest'
import {
  BRIDGE_CHANNEL,
  MAX_FRAME_HEIGHT,
  buildNativeDocument,
  createRenderCapability,
  isSafeAssetUrl,
  parseBridgeMessage,
} from './nativeBridge'

describe('native document bridge contract', () => {
  it('creates a fresh 128-bit hexadecimal capability', () => {
    const first = createRenderCapability()
    const second = createRenderCapability()

    expect(first).toMatch(/^[a-f0-9]{32}$/)
    expect(second).toMatch(/^[a-f0-9]{32}$/)
    expect(first).not.toBe(second)
  })

  it('injects an application bridge and bounded CSP without rewriting source colors', () => {
    const source = '<html><head><style>body{background:#fff;color:#123}</style></head><body><p>Entry</p></body></html>'
    const documentHtml = buildNativeDocument(source, 'a'.repeat(32))

    expect(documentHtml).toContain('Content-Security-Policy')
    expect(documentHtml).toContain("connect-src 'none'")
    expect(documentHtml).toContain('mdict-native-v1')
    expect(documentHtml).toContain('body{background:#fff;color:#123}')
    expect(documentHtml).not.toContain('invert(')
  })

  it('accepts only the expected capability and bounded typed payloads', () => {
    const capability = 'b'.repeat(32)
    const valid = parseBridgeMessage(
      {
        channel: BRIDGE_CHANNEL,
        capability,
        type: 'entry',
        payload: { word: 'right' },
      },
      capability,
    )
    const forged = parseBridgeMessage(
      {
        channel: BRIDGE_CHANNEL,
        capability: 'c'.repeat(32),
        type: 'entry',
        payload: { word: 'wrong' },
      },
      capability,
    )
    const oversizedHeight = parseBridgeMessage(
      {
        channel: BRIDGE_CHANNEL,
        capability,
        type: 'height',
        payload: { height: MAX_FRAME_HEIGHT + 1 },
      },
      capability,
    )
    const genericRpc = parseBridgeMessage(
      { channel: BRIDGE_CHANNEL, capability, type: 'eval', payload: { code: 'alert(1)' } },
      capability,
    )

    expect(valid?.type).toBe('entry')
    expect(forged).toBeNull()
    expect(oversizedHeight).toBeNull()
    expect(genericRpc).toBeNull()
  })

  it('allows only source capability or transitional legacy resource URLs', () => {
    expect(isSafeAssetUrl(`/assets/v2/${'a'.repeat(64)}`)).toBe(true)
    expect(isSafeAssetUrl('/mdict/uuid_FIXTURE/resource/sound.mp3')).toBe(true)
    expect(isSafeAssetUrl('https://attacker.invalid/audio.mp3')).toBe(false)
    expect(isSafeAssetUrl('javascript:alert(1)')).toBe(false)
  })
})
