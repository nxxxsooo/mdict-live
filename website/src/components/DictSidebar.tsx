import { useCallback, useRef } from 'react'
import { BookOpen, X } from 'lucide-react'
import { useDicts, useToggleDict } from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'

export function DictSidebar() {
  const { data: dicts = [] } = useDicts()
  const toggleDict = useToggleDict()
  const activeDict = useAppStore((s) => s.activeDict)
  const setActiveDict = useAppStore((s) => s.setActiveDict)
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen)
  const sidebarWidth = useAppStore((s) => s.sidebarWidth)
  const setSidebarWidth = useAppStore((s) => s.setSidebarWidth)

  const isDragging = useRef(false)

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault()
      isDragging.current = true
      document.body.classList.add('select-none')
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    },
    [],
  )

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!isDragging.current) return
      setSidebarWidth(e.clientX)
    },
    [setSidebarWidth],
  )

  const handlePointerUp = useCallback(() => {
    isDragging.current = false
    document.body.classList.remove('select-none')
  }, [])

  const realDicts = dicts.filter((d) => d.type !== 'app')

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed lg:sticky top-0 left-0 z-50 lg:z-auto h-screen bg-white border-r border-gray-200 flex flex-col transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ width: `${sidebarWidth}px` }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-blue-500" />
            <span className="font-semibold text-sm">Dictionaries</span>
          </div>
          <button
            className="lg:hidden p-1 rounded hover:bg-gray-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-2">
          {/* All dicts option */}
          <button
            onClick={() => {
              setActiveDict('all')
              setSidebarOpen(false)
            }}
            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
              activeDict === 'all'
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50'
            }`}
          >
            <span className="w-4 h-4 flex items-center justify-center text-xs">📚</span>
            All Dictionaries
          </button>

          <div className="my-2 border-t border-gray-100" />

          {realDicts.map((dict) => (
            <div key={dict.uuid} className="flex items-center group">
              <button
                onClick={() => {
                  setActiveDict(dict.uuid)
                  setSidebarOpen(false)
                }}
                className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeDict === dict.uuid
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                } ${!dict.enabled ? 'opacity-40' : ''}`}
              >
                <img
                  src={dict.logo}
                  alt=""
                  className="w-4 h-4 rounded flex-shrink-0"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
                <span className="truncate">{dict.title}</span>
              </button>
              {/* Toggle switch */}
              <button
                onClick={() => toggleDict.mutate(dict.uuid)}
                className={`flex-shrink-0 mr-2 w-8 h-4 rounded-full transition-colors relative ${
                  dict.enabled ? 'bg-blue-500' : 'bg-gray-300'
                }`}
                title={dict.enabled ? 'Disable' : 'Enable'}
              >
                <span
                  className={`absolute top-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform ${
                    dict.enabled ? 'translate-x-4' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          ))}
        </nav>

        <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100">
          {realDicts.length} dictionaries loaded
        </div>

        {/* Resize handle — desktop only */}
        <div
          className="hidden lg:block absolute top-0 right-0 w-1 h-full cursor-col-resize hover:w-1.5 hover:bg-blue-400/50 bg-transparent transition-all"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        />
      </aside>
    </>
  )
}
