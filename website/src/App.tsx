import { useEffect } from 'react'
import { Menu, Settings } from 'lucide-react'
import { SearchBar } from '@/components/SearchBar'
import { DictSidebar } from '@/components/DictSidebar'
import { ResultsArea } from '@/components/ResultsArea'
import { WordMeta } from '@/components/WordMeta'
import { useAppStore } from '@/stores/useAppStore'
import { SettingsPanel } from '@/components/SettingsPanel'

export default function App() {
  const searchWord = useAppStore((s) => s.searchWord)
  const setSearchWord = useAppStore((s) => s.setSearchWord)
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen)
  const darkMode = useAppStore((s) => s.darkMode)
  const toggleDarkMode = useAppStore((s) => s.toggleDarkMode)
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen)

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
            
            <a href="/" className="hidden sm:flex items-center gap-2 mr-2 group">
              <span className="font-bold text-xl text-slate-800 dark:text-slate-100 tracking-tight group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                Mdict<span className="text-blue-600 dark:text-blue-400">Live</span>
              </span>
            </a>

            <SearchBar />
            <button
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-500 dark:text-slate-400 transition-colors"
              onClick={() => setSettingsOpen(true)}
            >
              <Settings size={20} />
            </button>
          </div>
        </header>

        <div className="max-w-4xl mx-auto px-4 py-4 min-h-[calc(100vh-140px)]">
          {searchWord && <WordMeta word={searchWord} />}
          <ResultsArea />
        </div>

        <footer className="py-6 text-center text-sm text-gray-400 dark:text-slate-600 border-t border-gray-100 dark:border-slate-800/50 mt-auto">
          <p>
            Powered by <a href="https://mjshao.fun/work/mdict-live" target="_blank" rel="noopener noreferrer" className="hover:text-blue-500 transition-colors">MdictLive</a> • 
            A project by <a href="https://mjshao.fun" target="_blank" rel="noopener noreferrer" className="hover:text-blue-500 transition-colors">Mingjian Shao</a>
          </p>
        </footer>
      </main>

      <SettingsPanel />
    </div>
  )
}
