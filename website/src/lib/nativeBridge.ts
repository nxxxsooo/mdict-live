export const BRIDGE_CHANNEL = 'mdict-native-v1'
export const MIN_FRAME_HEIGHT = 96
export const MAX_FRAME_HEIGHT = 12_000
export const EMBEDDED_FRAME_HEIGHT = 2_200

export type NativeBridgeMessage =
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'ready'; payload: Record<string, never> }
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'height'; payload: { height: number } }
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'entry'; payload: { word: string } }
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'sound'; payload: { url: string } }
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'media'; payload: { url: string } }
  | { channel: typeof BRIDGE_CHANNEL; capability: string; type: 'resource-error'; payload: { kind: string } }

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function createRenderCapability(): string {
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function isSafeAssetUrl(value: string): boolean {
  return (
    /^\/(?:[A-Za-z0-9._~-]+\/)*assets\/v2\/[A-Za-z0-9_-]{32,4096}$/.test(value) ||
    /^\/(?:[A-Za-z0-9._~-]+\/)*mdict\/uuid_[A-Za-z0-9_-]+\/resource\//.test(value)
  )
}

export function parseBridgeMessage(
  value: unknown,
  expectedCapability: string,
): NativeBridgeMessage | null {
  if (!isRecord(value)) return null
  if (value.channel !== BRIDGE_CHANNEL || value.capability !== expectedCapability) return null
  if (typeof value.type !== 'string' || !isRecord(value.payload)) return null
  const base = {
    channel: BRIDGE_CHANNEL,
    capability: expectedCapability,
  } as const
  switch (value.type) {
    case 'ready':
      return { ...base, type: 'ready', payload: {} }
    case 'height': {
      const height = value.payload.height
      if (typeof height !== 'number' || !Number.isFinite(height)) return null
      if (height < MIN_FRAME_HEIGHT || height > MAX_FRAME_HEIGHT) return null
      return { ...base, type: 'height', payload: { height: Math.round(height) } }
    }
    case 'entry': {
      const word = value.payload.word
      if (typeof word !== 'string' || !word.trim() || [...word.trim()].length > 256) return null
      return { ...base, type: 'entry', payload: { word: word.trim() } }
    }
    case 'sound':
    case 'media': {
      const url = value.payload.url
      if (typeof url !== 'string' || !isSafeAssetUrl(url)) return null
      return { ...base, type: value.type, payload: { url } }
    }
    case 'resource-error': {
      const kind = value.payload.kind
      if (typeof kind !== 'string' || kind.length > 32) return null
      return { ...base, type: 'resource-error', payload: { kind } }
    }
    default:
      return null
  }
}

const CSP = [
  "default-src 'none'",
  "script-src 'unsafe-inline'",
  "style-src 'unsafe-inline' http: https:",
  'img-src data: blob: http: https:',
  'font-src data: http: https:',
  'media-src data: blob: http: https:',
  "connect-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
].join('; ')

function bridgeScript(capability: string): string {
  return `<script>
(() => {
  'use strict';
  const channel = ${JSON.stringify(BRIDGE_CHANNEL)};
  const capability = ${JSON.stringify(capability)};
  const send = (type, payload) => parent.postMessage({ channel, capability, type, payload }, '*');
  const height = () => {
    const value = Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight || 0);
    send('height', { height: Math.min(${MAX_FRAME_HEIGHT}, Math.max(${MIN_FRAME_HEIGHT}, value)) });
  };
  const reportSoon = () => requestAnimationFrame(() => requestAnimationFrame(height));
  document.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target.closest('a,button') : null;
    if (!target) return;
    const action = target.getAttribute('data-mdict-action');
    if (target instanceof HTMLAnchorElement) event.preventDefault();
    if (action === 'entry') {
      send('entry', { word: target.getAttribute('data-mdict-entry') || '' });
    } else if (action === 'sound') {
      send('sound', { url: target.getAttribute('data-mdict-resource') || '' });
    } else if (action === 'media') {
      send('media', { url: target.getAttribute('data-mdict-resource') || '' });
    }
  }, true);
  document.addEventListener('submit', (event) => event.preventDefault(), true);
  window.addEventListener('error', (event) => {
    const target = event.target;
    if (target instanceof HTMLImageElement || target instanceof HTMLLinkElement || target instanceof HTMLMediaElement) {
      send('resource-error', { kind: target.tagName.toLowerCase() });
    }
  }, true);
  new MutationObserver(reportSoon).observe(document.documentElement, { childList: true, subtree: true, attributes: true });
  if ('ResizeObserver' in window) new ResizeObserver(reportSoon).observe(document.documentElement);
  document.fonts?.ready.then(reportSoon).catch(() => {});
  window.addEventListener('load', reportSoon, { once: true });
  send('ready', {});
  reportSoon();
})();
</script>`
}

export function buildNativeDocument(safeHtml: string, capability: string): string {
  const csp = `<meta http-equiv="Content-Security-Policy" content="${CSP}">`
  const viewport = '<meta name="viewport" content="width=device-width, initial-scale=1">'
  const baseline = `<style>
html { color-scheme: light; background: #fff; }
body { margin: 0; padding: 18px; overflow-wrap: anywhere; }
img, video, table { max-width: 100%; }
img, video { height: auto; }
button[disabled], input[disabled], select[disabled], textarea[disabled] { pointer-events: none; }
</style>`
  const bridge = bridgeScript(capability)
  if (/<html[\s>]/i.test(safeHtml)) {
    let documentHtml = safeHtml
    if (/<head[\s>]/i.test(documentHtml)) {
      documentHtml = documentHtml.replace(/<head([^>]*)>/i, `<head$1>${csp}${viewport}${baseline}`)
    } else {
      documentHtml = documentHtml.replace(/<html([^>]*)>/i, `<html$1><head>${csp}${viewport}${baseline}</head>`)
    }
    if (/<\/body>/i.test(documentHtml)) return documentHtml.replace(/<\/body>/i, `${bridge}</body>`)
    return `${documentHtml}${bridge}`
  }
  return `<!doctype html><html><head>${csp}${viewport}${baseline}</head><body>${safeHtml}${bridge}</body></html>`
}
