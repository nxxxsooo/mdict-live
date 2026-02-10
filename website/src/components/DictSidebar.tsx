import { useCallback, useRef, useState } from 'react'
import { BookOpen, X, History, Trash2, Bookmark, Plus, ArrowLeft, MoreVertical } from 'lucide-react'
import {
  useDicts,
  useToggleDict,
  useHistory,
  useClearHistory,
  useWordbooks,
  useWordbookEntries,
  useCreateWordbook,
  useDeleteWordbook,
  useDeleteWordbookEntry,
} from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'

export function DictSidebar() {
  const { data: dicts = [] } = useDicts()
  const toggleDict = useToggleDict()
  const { data: history = [] } = useHistory()
  const clearHistory = useClearHistory()

  const { data: wordbooks = [] } = useWordbooks()
  const createWordbook = useCreateWordbook()
  const deleteWordbook = useDeleteWordbook()
  const deleteEntry = useDeleteWordbookEntry()

  const [selectedWbId, setSelectedWbId] = useState<number | null>(null)
  const { data: wbEntries = [] } = useWordbookEntries(selectedWbId || 0)

  const activeDict = useAppStore((s) => s.activeDict)
  const setActiveDict = useAppStore((s) => s.setActiveDict)
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen)
  const sidebarWidth = useAppStore((s) => s.sidebarWidth)
  const setSidebarWidth = useAppStore((s) => s.setSidebarWidth)
  const activeTab = useAppStore((s) => s.activeSidebarTab)
  const setActiveTab = useAppStore((s) => s.setActiveSidebarTab)
  const setSearchWord = useAppStore((s) => s.setSearchWord)

  const isDragging = useRef(false)

  const handleCreateWordbook = () => {
    const name = prompt('Enter wordbook name:')
    if (name) createWordbook.mutate(name)
  }

  const handleDeleteWordbook = (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    if (confirm('Delete this wordbook?')) deleteWordbook.mutate(id)
  }

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
        className={`fixed lg:sticky top-0 left-0 z-50 lg:z-auto h-screen bg-white dark:bg-slate-900 border-r border-gray-200 dark:border-slate-800 flex flex-col transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ width: `${sidebarWidth}px` }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-slate-800">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab('dicts')}
              className={`flex items-center gap-2 pb-1 border-b-2 transition-colors ${
                activeTab === 'dicts'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              <BookOpen size={18} />
              <span className="font-semibold text-sm">Dicts</span>
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex items-center gap-2 pb-1 border-b-2 transition-colors ${
                activeTab === 'history'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              <History size={18} />
              <span className="font-semibold text-sm">History</span>
            </button>
            <button
              onClick={() => setActiveTab('wordbook')}
              className={`flex items-center gap-2 pb-1 border-b-2 transition-colors ${
                activeTab === 'wordbook'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-slate-400 dark:hover:text-slate-200'
              }`}
            >
              <Bookmark size={18} />
              <span className="font-semibold text-sm">Wordbook</span>
            </button>
          </div>
          <button
            className="lg:hidden p-1 rounded hover:bg-gray-100 dark:hover:bg-slate-800 dark:text-slate-400"
            onClick={() => setSidebarOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-2">
          {activeTab === 'dicts' ? (
            <>
              {/* All dicts option */}
              <button
                onClick={() => {
                  setActiveDict('all')
                  setSidebarOpen(false)
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeDict === 'all'
                    ? 'bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-400'
                    : 'text-gray-600 hover:bg-gray-50 dark:text-slate-400 dark:hover:bg-slate-800'
                }`}
              >
                <span className="w-4 h-4 flex items-center justify-center text-xs">📚</span>
                All Dictionaries
              </button>

              <div className="my-2 border-t border-gray-100 dark:border-slate-800" />

              {realDicts.map((dict) => (
                <div key={dict.uuid} className="flex items-center group">
                  <button
                    onClick={() => {
                      setActiveDict(dict.uuid)
                      setSidebarOpen(false)
                    }}
                    className={`flex-1 flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                      activeDict === dict.uuid
                        ? 'bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-400'
                        : 'text-gray-600 hover:bg-gray-50 dark:text-slate-400 dark:hover:bg-slate-800'
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
                      dict.enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-slate-700'
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
            </>
          ) : activeTab === 'history' ? (
            <div className="space-y-1">
              <div className="flex justify-end px-2 mb-2">
                <button
                  onClick={() => clearHistory.mutate()}
                  className="flex items-center gap-1 text-xs text-gray-400 hover:text-red-500 dark:text-slate-500 dark:hover:text-red-400 transition-colors"
                >
                  <Trash2 size={12} />
                  Clear
                </button>
              </div>
              {history.map((item) => (
                <button
                  key={item.word}
                  onClick={() => {
                    setSearchWord(item.word)
                    setSidebarOpen(false)
                  }}
                  className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                >
                  {item.word}
                </button>
              ))}
              {history.length === 0 && (
                <div className="text-center py-8 text-sm text-gray-400 dark:text-slate-600">
                  No history yet
                </div>
              )}
            </div>
          ) : (
            // Wordbook Tab
            <div className="space-y-1 h-full flex flex-col">
              {selectedWbId === null ? (
                // Wordbook List
                <>
                  <div className="flex justify-between items-center px-2 mb-2">
                    <span className="text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                      My Wordbooks
                    </span>
                    <button
                      onClick={handleCreateWordbook}
                      className="p-1 text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                      title="Create Wordbook"
                    >
                      <Plus size={16} />
                    </button>
                  </div>
                  {wordbooks.map((wb) => (
                    <div
                      key={wb.id}
                      onClick={() => setSelectedWbId(wb.id)}
                      className="group flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Bookmark size={14} />
                        <span>{wb.name}</span>
                      </div>
                      <button
                        onClick={(e) => handleDeleteWordbook(e, wb.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-all"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                  {wordbooks.length === 0 && (
                    <div className="text-center py-8 text-sm text-gray-400 dark:text-slate-600">
                      No wordbooks
                    </div>
                  )}
                </>
              ) : (
                // Entries List
                <>
                  <div className="flex items-center gap-2 px-2 mb-2 pb-2 border-b border-gray-100 dark:border-slate-800">
                    <button
                      onClick={() => setSelectedWbId(null)}
                      className="p-1 -ml-1 text-gray-500 hover:bg-gray-100 dark:text-slate-400 dark:hover:bg-slate-800 rounded"
                    >
                      <ArrowLeft size={16} />
                    </button>
                    <span className="font-medium text-sm dark:text-slate-200">
                      {wordbooks.find((w) => w.id === selectedWbId)?.name}
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto">
                    {wbEntries.map((entry) => (
                      <div
                        key={entry.id}
                        className="group flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                      >
                        <button
                          className="flex-1 text-left"
                          onClick={() => {
                            setSearchWord(entry.word)
                            setSidebarOpen(false)
                          }}
                        >
                          {entry.word}
                        </button>
                        <button
                          onClick={() =>
                            deleteEntry.mutate({ wbId: selectedWbId, entryId: entry.id })
                          }
                          className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-all"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                    {wbEntries.length === 0 && (
                      <div className="text-center py-8 text-sm text-gray-400 dark:text-slate-600">
                        Empty wordbook
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </nav>

        <div className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100 dark:border-slate-800">
          {activeTab === 'dicts'
            ? `${realDicts.length} dictionaries`
            : activeTab === 'history'
            ? `${history.length} history items`
            : selectedWbId === null
            ? `${wordbooks.length} wordbooks`
            : `${wbEntries.length} words`}
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
