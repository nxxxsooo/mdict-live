import { useRef, useEffect, useState } from 'react'
import { useAppStore } from '@/stores/useAppStore'

interface DictPanelProps {
  uuid: string
  title: string
  logo?: string
  html: string
}

export function DictPanel({ uuid, title, logo, html }: DictPanelProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(200)
  const darkMode = useAppStore((s) => s.darkMode)

  // Build full HTML document for the iframe
  const iframeDoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background-color: white; color: black; }
    img { max-width: 100%; height: auto; }
    a[data-entry-word] { color: #2563eb; text-decoration: none; cursor: pointer; }
    a[data-entry-word]:hover { text-decoration: underline; }
    a[data-sound-url] { cursor: pointer; }
    /* Dark mode: invert everything but restore images */
    html.dark body { filter: invert(1) hue-rotate(180deg); }
    html.dark img, html.dark video { filter: invert(1) hue-rotate(180deg); }
  </style>
</head>
<body>
  <div id="class_${uuid}">
    <div class="mdict">${html}</div>
  </div>
  <script>
    // Listen for theme changes from parent
    window.addEventListener('message', (e) => {
      if (e.data.type === 'theme') {
        if (e.data.dark) document.documentElement.classList.add('dark');
        else document.documentElement.classList.remove('dark');
      }
    });
    // Request initial theme
    window.parent.postMessage({ type: 'request-theme', uuid: '${uuid}' }, '*');

    // Auto-resize: notify parent of content height
    function notifyHeight() {
      const h = document.documentElement.scrollHeight;
      window.parent.postMessage({ type: 'iframe-resize', uuid: '${uuid}', height: h }, '*');
    }
    // Observe DOM changes for dynamic content
    const observer = new MutationObserver(notifyHeight);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    window.addEventListener('load', () => setTimeout(notifyHeight, 100));
    notifyHeight();

    // Handle entry:// links - navigate in parent
    document.addEventListener('click', (e) => {
      const link = e.target.closest('a');
      if (!link) return;
      const entryWord = link.getAttribute('data-entry-word');
      if (entryWord) {
        e.preventDefault();
        // Clean up the word (remove trailing quotes from regex)
        const word = entryWord.replace(/^["']|["']$/g, '');
        window.parent.postMessage({ type: 'entry-click', word: word }, '*');
        return;
      }
      const soundUrl = link.getAttribute('data-sound-url');
      if (soundUrl) {
        e.preventDefault();
        const url = soundUrl.replace(/^["']|["']$/g, '');
        const audio = new Audio(url);
        audio.play().catch(() => {});
        return;
      }
    });
  </script>
</body>
</html>`

  // Listen for resize messages
  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (e.data?.type === 'iframe-resize' && e.data.uuid === uuid) {
        setHeight(Math.max(e.data.height + 20, 100))
      }
      if (e.data?.type === 'request-theme' && e.data.uuid === uuid) {
         iframeRef.current?.contentWindow?.postMessage({ type: 'theme', dark: darkMode }, '*')
      }
      if (e.data?.type === 'entry-click' && e.data.word) {
        // Dispatch custom event for the app to handle
        window.dispatchEvent(
          new CustomEvent('dict-entry-click', { detail: { word: e.data.word } }),
        )
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [uuid, darkMode])

  // Sync theme when darkMode changes
  useEffect(() => {
    iframeRef.current?.contentWindow?.postMessage({ type: 'theme', dark: darkMode }, '*')
  }, [darkMode])

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-800 shadow-sm overflow-hidden mb-4 transition-colors">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700 transition-colors">
        {logo && (
          <img
            src={logo}
            alt=""
            className="w-4 h-4 rounded"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        )}
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">{title}</span>
      </div>
      <iframe
        ref={iframeRef}
        srcDoc={iframeDoc}
        sandbox="allow-same-origin allow-scripts allow-popups"
        style={{ width: '100%', height: `${height}px`, border: 'none' }}
        title={title}
      />
    </div>
  )
}
