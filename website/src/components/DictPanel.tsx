import { useRef, useEffect, useState } from 'react'

interface DictPanelProps {
  uuid: string
  title: string
  logo?: string
  html: string
}

export function DictPanel({ uuid, title, logo, html }: DictPanelProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(200)

  // Build full HTML document for the iframe
  const iframeDoc = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    img { max-width: 100%; height: auto; }
    a[data-entry-word] { color: #2563eb; text-decoration: none; cursor: pointer; }
    a[data-entry-word]:hover { text-decoration: underline; }
    a[data-sound-url] { cursor: pointer; }
  </style>
</head>
<body>
  <div id="class_${uuid}">
    <div class="mdict">${html}</div>
  </div>
  <script>
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
      if (e.data?.type === 'entry-click' && e.data.word) {
        // Dispatch custom event for the app to handle
        window.dispatchEvent(
          new CustomEvent('dict-entry-click', { detail: { word: e.data.word } }),
        )
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [uuid])

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-4">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-50 border-b border-gray-100">
        {logo && (
          <img
            src={logo}
            alt=""
            className="w-4 h-4 rounded"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        )}
        <span className="text-sm font-medium text-gray-700">{title}</span>
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
