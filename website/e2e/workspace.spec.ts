import { expect, test, type Page, type Route } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'

const TOKEN = 'private-test-token-0123456789abcdef'
const ASSET_CAPABILITY = 'a'.repeat(48)

interface LookupEntryFixture {
  sourceId: string
  revision: string
  entryId: string
  html: string
  text: string
}

const sources = [
  {
    source_id: 'src_oald',
    revision: 'rev_oald_real_shape_001',
    title: 'OALD 10',
    enabled: true,
    order: 0,
    available: true,
  },
  {
    source_id: 'src_grid',
    revision: 'rev_grid_fixture_001',
    title: 'Lexicon Grid',
    enabled: true,
    order: 1,
    available: true,
  },
  {
    source_id: 'src_delayed',
    revision: 'rev_delayed_fixture_001',
    title: 'Delayed source',
    enabled: true,
    order: 2,
    available: false,
    unavailable_reason: 'Index unavailable',
  },
]

function envelope<T>(requestId: string, data: T) {
  return { api_version: '2.0', request_id: requestId, data }
}

function entry(fixture: LookupEntryFixture) {
  const citation = {
    uri: `mdict://${fixture.sourceId}/${fixture.entryId}`,
    token: `citation-${fixture.entryId}`,
  }
  return {
    source_id: fixture.sourceId,
    revision: fixture.revision,
    entry_id: fixture.entryId,
    headword: fixture.entryId === 'entry_wrong' ? 'wrong' : 'right',
    record_ordinal: 0,
    citation,
    html: fixture.html,
    text_blocks: [
      {
        block_id: `${fixture.entryId}-definition`,
        order: 0,
        text: fixture.text,
        citation: { ...citation, uri: `${citation.uri}#definition` },
      },
    ],
  }
}

const rightEntries = [
  entry({
    sourceId: 'src_oald',
    revision: 'rev_oald_real_shape_001',
    entryId: 'entry_right',
    text: 'True or correct as a fact.',
    html: `<style>
      html { background: #fff; }
      body { color: #7f1d1d; background: #fff; font: 17px/1.5 Georgia, serif; }
      .entry { display: block; border-top: 3px solid #ef4444; }
      .sense { margin: 14px 0; }
      table { border-collapse: collapse; width: 100%; }
      td { border: 1px solid #e5b8b8; padding: 8px; }
    </style>
    <article class="entry">
      <h1>right</h1>
      <p class="sense"><strong>true/correct</strong> · 真实；正确</p>
      <p>True or correct as a fact.</p>
      <table><tbody><tr><td>grammar</td><td>adjective · adverb · noun · verb</td></tr></tbody></table>
      <a href="#" data-mdict-action="sound" data-mdict-resource="/assets/v2/${ASSET_CAPABILITY}">Play pronunciation</a>
    </article>`,
  }),
  entry({
    sourceId: 'src_grid',
    revision: 'rev_grid_fixture_001',
    entryId: 'entry_grid_right',
    text: 'Suitable for a particular purpose.',
    html: `<style>
      html { background: #fff; }
      body { color: #1d4ed8; background: #fff; font: 15px/1.55 system-ui; }
      .entry { display: grid; grid-template-columns: 8rem 1fr; gap: 12px; }
      a { color: #0f766e; }
    </style>
    <article class="entry">
      <strong>right</strong><span>Suitable for a particular purpose.</span>
      <strong>opposite</strong><a href="#" data-mdict-action="entry" data-mdict-entry="wrong">wrong</a>
    </article>`,
  }),
]

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

async function installApi(page: Page, defaultEntries = rightEntries) {
  await page.addInitScript((token) => {
    if (window.top !== window) return
    sessionStorage.setItem('mdictLiveV2Token', token)
    Object.defineProperty(window, '__playedUrls', { value: [], writable: true })
    class TestAudio {
      constructor(url: string) {
        ;(window as Window & { __playedUrls: string[] }).__playedUrls.push(url)
      }
      play() { return Promise.resolve() }
    }
    Object.defineProperty(window, 'Audio', { value: TestAudio, configurable: true })
  }, TOKEN)

  await page.route(/^http:\/\/127\.0\.0\.1:4180\/assets\/v2\//, (route) =>
    route.fulfill({ status: 200, contentType: 'audio/mpeg', body: '' }),
  )
  await page.route(/^http:\/\/127\.0\.0\.1:4180\/api\//, async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path === '/api/v2/sources') {
      return fulfillJson(route, envelope('req_sources', { sources }))
    }
    if (path === '/api/v2/suggestions') {
      return fulfillJson(route, envelope('req_suggestions', {
        suggestions: [{ headword: 'right' }, { headword: 'rigid' }],
      }))
    }
    if (path === '/api/v2/metadata') {
      const query = url.searchParams.get('q') ?? ''
      return fulfillJson(route, envelope('req_metadata', {
        available: query !== 'absent',
        query,
        records: query === 'absent' ? [] : [{
          dataset: { id: 'ecdict', title: 'ECDICT lexical metadata', version: 'fixture-1' },
          phonetic: query === 'right' ? 'raɪt' : undefined,
          definition: query === 'wrong' ? 'Not correct.' : 'Correct, suitable, or morally good.',
          translation: query === 'right' ? '正确的；合适的；右边的' : undefined,
          tags: ['fixture'],
        }],
      }))
    }
    if (path === '/api/v2/lookup') {
      const payload = request.postDataJSON() as { query: string }
      const query = payload.query.trim()
      if (query === 'failure') {
        return fulfillJson(route, {
          api_version: '2.0',
          request_id: 'req_failure',
          error: { code: 'lookup_unavailable', message: 'No selected source completed.' },
        }, 503)
      }
      const entries = query === 'absent'
        ? []
        : query === 'wrong'
          ? [entry({
              sourceId: 'src_grid',
              revision: 'rev_grid_fixture_001',
              entryId: 'entry_wrong',
              text: 'Not correct.',
              html: '<style>html,body{background:#fff;color:#1d4ed8}</style><article><h1>wrong</h1><p>Not correct.</p></article>',
            })]
          : defaultEntries
      const partial = query === 'partial'
      return fulfillJson(route, envelope(`req_lookup_${query}`, {
        query,
        normalized_query: query,
        entries: partial ? entries.slice(0, 1) : entries,
        partial,
        truncated: false,
        truncation: null,
        history_recorded: true,
        progress: {
          completed_source_ids: partial ? ['src_oald'] : ['src_oald', 'src_grid'],
          failed_sources: partial
            ? [{ source_id: 'src_grid', code: 'timeout', message: 'Source timed out.' }]
            : [],
          omitted_source_ids: partial ? ['src_grid'] : [],
        },
      }))
    }
    if (path === '/api/history') return fulfillJson(route, [])
    if (path === '/api/wordbooks/entries') return fulfillJson(route, [])
    if (path === '/api/wordbooks') return fulfillJson(route, [])
    return fulfillJson(route, { ok: true })
  })
}

async function search(page: Page, query: string) {
  const input = page.getByRole('combobox')
  await input.fill(query)
  await input.press('Enter')
}

test('desktop workspace isolates source CSS and accepts only typed native actions', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  await installApi(page)
  await page.goto('./')
  await search(page, 'right')

  await expect(page.getByRole('heading', { name: 'right', level: 1 })).toBeVisible()
  await expect(page.getByLabel('Quick sense')).toContainText('A quick sense')
  await expect(page.getByLabel('Quick sense')).toContainText('True or correct as a fact.')
  await expect(page.getByRole('heading', { name: 'OALD 10', level: 2 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Lexicon Grid', level: 2 })).toBeVisible()

  const oaldFrame = page.frameLocator('iframe[title="OALD 10: right"]')
  const gridFrame = page.frameLocator('iframe[title="Lexicon Grid: right"]')
  await expect(oaldFrame.locator('body')).toHaveCSS('color', 'rgb(127, 29, 29)')
  await expect(gridFrame.locator('body')).toHaveCSS('color', 'rgb(29, 78, 216)')
  await expect(oaldFrame.locator('.entry')).toHaveCSS('display', 'block')
  await expect(gridFrame.locator('.entry')).toHaveCSS('display', 'grid')

  const firstFrame = page.locator('iframe[title="OALD 10: right"]')
  const heightBefore = Number.parseInt(await firstFrame.evaluate((node) => (node as HTMLIFrameElement).style.height), 10)
  await oaldFrame.locator('body').evaluate((body) => {
    const delayed = document.createElement('div')
    delayed.style.height = '720px'
    delayed.textContent = 'Delayed content'
    body.append(delayed)
  })
  await expect.poll(async () => Number.parseInt(await firstFrame.evaluate((node) => (node as HTMLIFrameElement).style.height), 10)).toBeGreaterThan(heightBefore)

  await oaldFrame.getByRole('link', { name: 'Play pronunciation' }).click()
  await expect.poll(() => page.evaluate(() => (window as Window & { __playedUrls: string[] }).__playedUrls)).toContain(`/assets/v2/${ASSET_CAPABILITY}`)

  await page.evaluate(() => window.postMessage({
    channel: 'mdict-native-v1',
    capability: 'f'.repeat(32),
    type: 'entry',
    payload: { word: 'forged' },
  }, '*'))
  await expect(page.getByRole('combobox')).toHaveValue('right')

  await gridFrame.getByRole('link', { name: 'wrong' }).click()
  await expect(page.getByRole('heading', { name: 'wrong', level: 1 })).toBeVisible()

  await page.getByRole('button', { name: 'Use dark workspace' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect(page.frameLocator('iframe[title="Lexicon Grid: wrong"]').locator('body')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  expect(await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('body *'))
    .filter((element) => {
      const rect = element.getBoundingClientRect()
      return rect.right > document.documentElement.clientWidth + 1
    })
    .map((element) => ({
      tag: element.tagName,
      className: element.className,
      left: element.getBoundingClientRect().left,
      right: element.getBoundingClientRect().right,
    })))).toEqual([])
  expect(consoleErrors).toEqual([])
})

test('lookup states distinguish partial evidence, no match, and total failure', async ({ page }) => {
  await installApi(page)
  await page.goto('./')

  await search(page, 'partial')
  await expect(page.getByText('Partial evidence')).toBeVisible()
  await expect(page.getByText(/Lexicon Grid: timeout/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'OALD 10', level: 2 })).toBeVisible()

  await search(page, 'absent')
  await expect(page.getByText('No dictionary match')).toBeVisible()
  await expect(page.getByText(/returned no entry/)).toBeVisible()

  await search(page, 'failure')
  await expect(page.getByText('Lookup unavailable')).toBeVisible()
  await expect(page.getByText('No selected source completed.')).toBeVisible()
})

test('phone navigation is off-canvas, inert when hidden, and returns focus', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installApi(page)
  await page.goto('./')
  await search(page, 'right')

  const navigation = page.getByLabel('Dictionary workspace navigation')
  await expect(navigation).toHaveAttribute('inert', '')
  const menuButton = page.getByRole('button', { name: 'Open source navigation' })
  await menuButton.click()
  await expect(navigation).not.toHaveAttribute('inert', '')
  await expect(page.getByRole('button', { name: /OALD 10 Result available/ })).toBeVisible()
  await page.getByRole('button', { name: 'Close navigation' }).click()
  await expect(menuButton).toBeFocused()
  await expect(navigation).toHaveAttribute('inert', '')

  const contextButton = page.getByRole('button', { name: 'Open context' })
  await contextButton.click()
  await expect(page.getByRole('dialog', { name: 'Context and agent guidance' })).toBeVisible()
  await page.getByRole('button', { name: 'Close context panel' }).click()
  await expect(contextButton).toBeFocused()

  await page.keyboard.press('Control+K')
  await expect(page.getByRole('combobox')).toBeFocused()
  expect(await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('body *'))
    .filter((element) => {
      const rect = element.getBoundingClientRect()
      return rect.right > document.documentElement.clientWidth + 1
    })
    .map((element) => ({
      tag: element.tagName,
      className: element.className,
      left: element.getBoundingClientRect().left,
      right: element.getBoundingClientRect().right,
    })))).toEqual([])
  expect(await page.evaluate(() => ({
    scrollX: window.scrollX,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))).toEqual({ scrollX: 0, scrollWidth: 390, clientWidth: 390 })
  const frameWidth = await page.locator('iframe[title="OALD 10: right"]').evaluate((node) => node.getBoundingClientRect().width)
  expect(frameWidth).toBeLessThanOrEqual(390)
})

const realEntryPath = process.env.MDICT_REAL_ENTRY_HTML
test('manual real-corpus fixture preserves native complexity and the safe boundary', async ({ page }) => {
  test.skip(!realEntryPath || !existsSync(realEntryPath), 'Set MDICT_REAL_ENTRY_HTML to an extracted sanitized entry.')
  const realHtml = readFileSync(realEntryPath!, 'utf8')
    .replace(/<meta\s+http-equiv="Content-Security-Policy"[^>]*>/i, '')
    .replace(/<script\s+nonce="mdict-fixture-bridge">[\s\S]*?<\/script>/i, '')
    .replace(/data-entry-word="([^"]*)"/g, 'data-mdict-action="entry" data-mdict-entry="$1"')
    .replace(/data-sound-url="[^"]*"/g, `data-mdict-action="sound" data-mdict-resource="/assets/v2/${ASSET_CAPABILITY}"`)
  const realEntry = entry({
    sourceId: 'src_oald',
    revision: 'rev_oald_real_extract_001',
    entryId: 'entry_right_real',
    text: 'True or correct as a fact.',
    html: realHtml,
  })
  const consoleErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await installApi(page, [realEntry])
  await page.goto('./')
  await search(page, 'right')

  await expect(page.getByLabel('Quick sense')).toContainText('First source sense · OALD 10')
  const frame = page.frameLocator('iframe[title="OALD 10: right"]')
  await expect(frame.locator('h1.headword').first()).toHaveCSS('color', 'rgb(255, 0, 0)')
  const shape = await frame.locator('body').evaluate((body) => ({
    tags: body.querySelectorAll('*').length,
    ids: body.querySelectorAll('[id]').length,
    classes: new Set(Array.from(body.querySelectorAll('[class]')).flatMap((element) => Array.from(element.classList))).size,
    tables: body.querySelectorAll('table').length,
    entryLinks: body.querySelectorAll('[data-mdict-action="entry"]').length,
    soundLinks: body.querySelectorAll('[data-mdict-action="sound"]').length,
    sourceScripts: Array.from(body.querySelectorAll('script')).filter((script) => !script.textContent?.includes('mdict-native-v1')).length,
    inlineHandlers: Array.from(body.querySelectorAll('*')).reduce((count, element) =>
      count + Array.from(element.attributes).filter((attribute) => attribute.name.startsWith('on')).length, 0),
  }))
  expect(shape).toMatchObject({ tables: 1, sourceScripts: 0, inlineHandlers: 0 })
  expect(shape.tags).toBeGreaterThan(4_000)
  expect(shape.ids).toBeGreaterThan(250)
  expect(shape.classes).toBeGreaterThan(80)
  expect(shape.entryLinks).toBeGreaterThan(150)
  expect(shape.soundLinks).toBeGreaterThan(200)

  await expect(page.getByRole('button', { name: 'Full source view' })).toBeVisible()
  await page.getByRole('button', { name: 'Full source view' }).click()
  await expect(page.getByRole('dialog', { name: /OALD 10 full source/ })).toBeVisible()
  await page.getByRole('button', { name: 'Return to results' }).click()
  await expect(page.getByRole('button', { name: 'Full source view' })).toBeFocused()

  await frame.locator('[data-mdict-action="sound"]').first().click()
  await expect.poll(() => page.evaluate(() => (window as Window & { __playedUrls: string[] }).__playedUrls.length)).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Use dark workspace' }).click()
  await expect(frame.locator('html')).toHaveCSS('background-color', 'rgb(255, 255, 255)')

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('iframe[title="OALD 10: right"]')).toBeVisible()
  expect(await page.evaluate(() => ({
    scrollX: window.scrollX,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))).toEqual({ scrollX: 0, scrollWidth: 390, clientWidth: 390 })
  expect(consoleErrors).toEqual([])
})
