import { useEffect } from 'react'
import { Menu } from 'lucide-react'
import { SearchBar } from '@/components/SearchBar'
import { DictSidebar } from '@/components/DictSidebar'
import { ResultsArea } from '@/components/ResultsArea'
import { HistoryPanel } from '@/components/HistoryPanel'
import { WordMeta } from '@/components/WordMeta'
import { useAppStore } from '@/stores/useAppStore'

export default function App() {
  const searchWord = useAppStore((s) => s.searchWord)
  const setSearchWord = useAppStore((s) => s.setSearchWord)
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen)
  const darkMode = useAppStore((s) => s.darkMode)
  const toggleDarkMode = useAppStore((s) => s.toggleDarkMode)

  // Sync dark mode class
  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  // Keyboard shortcut Ctrl+Shift+D
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'd') {
        e.preventDefault()
        toggleDarkMode()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggleDarkMode])

  // Handle entry:// clicks from dict iframes
  useEffect(() => {
    function handleEntryClick(e: Event) {
      const word = (e as CustomEvent).detail?.word
      if (word) setSearchWord(word)
    }
    window.addEventListener('dict-entry-click', handleEntryClick)
    return () => window.removeEventListener('dict-entry-click', handleEntryClick)
  }, [setSearchWord])

  return (
    <div className="flex min-h-screen">
      <DictSidebar />

      <main className="flex-1 min-w-0 bg-slate-50 dark:bg-slate-950 transition-colors">
        {/* Header */}
        <header className="sticky top-0 z-30 bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm border-b border-gray-200 dark:border-slate-800 transition-colors">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
            <button
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800 dark:text-slate-200 transition-colors"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu size={20} />
            </button>
            <SearchBar />
          </div>
        </header>

        {/* Content */}
        <div className="max-w-4xl mx-auto px-4 py-4">
          {searchWord && <WordMeta word={searchWord} />}
          <ResultsArea />
          <HistoryPanel />
        </div>
      </main>
    </div>
  )
}
