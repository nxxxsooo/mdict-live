import { describe, expect, it } from 'vitest'
import { publicPrefix, rebaseSourceResources } from './basePath'

describe('reverse-prefix browser paths', () => {
  it('derives only the path before the application mount', () => {
    expect(publicPrefix('/app/')).toBe('')
    expect(publicPrefix('/private/dictionary/app/')).toBe('/private/dictionary')
    expect(publicPrefix('/not-the-workspace')).toBe('')
  })

  it('rebases only known source resource paths under a public prefix', () => {
    window.history.replaceState({}, '', '/private/dictionary/app/')
    const html = rebaseSourceResources(`
      <img src="/assets/v2/${'a'.repeat(40)}">
      <a data-mdict-resource="/mdict/uuid_fixture/resource/sound.mp3"></a>
      <a href="https://example.com/assets/v2/external"></a>
    `)

    expect(html).toContain(`/private/dictionary/assets/v2/${'a'.repeat(40)}`)
    expect(html).toContain('/private/dictionary/mdict/uuid_fixture/resource/sound.mp3')
    expect(html).toContain('https://example.com/assets/v2/external')
    window.history.replaceState({}, '', '/')
  })
})
