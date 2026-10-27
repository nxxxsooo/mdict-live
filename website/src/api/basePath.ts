export function publicPrefix(pathname = window.location.pathname): string {
  const match = pathname.match(/^(.*)\/app(?:\/|$)/)
  if (!match) return ''
  const prefix = match[1].replace(/\/$/, '')
  return prefix === '/' ? '' : prefix
}

export function servicePath(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${publicPrefix()}${normalized}`
}

export function rebaseSourceResources(html: string): string {
  const prefix = publicPrefix()
  if (!prefix) return html
  return html.replace(
    /(["'(=\s])\/(assets\/v2\/|mdict\/)/g,
    (_match, lead: string, resourcePath: string) => `${lead}${prefix}/${resourcePath}`,
  )
}
