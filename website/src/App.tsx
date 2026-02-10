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

      <main className="flex-1 min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-sm border-b border-gray-200">
          <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
            <button
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
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
