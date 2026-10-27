import { useEffect, useRef } from 'react'
import { Bookmark, Menu, MessageSquareText, Moon, Settings, Sun } from 'lucide-react'
import { SearchBar } from '@/components/SearchBar'
import { SourceLedger } from '@/components/SourceLedger'
import { ReadingWorkspace } from '@/components/ReadingWorkspace'
import { ContextDrawer } from '@/components/ContextDrawer'
import { SettingsPanel } from '@/components/SettingsPanel'
import { useWorkspaceLookup } from '@/hooks/useWorkspace'
import { useAppStore } from '@/stores/useAppStore'

export default function App() {
  const searchWord = useAppStore((state) => state.searchWord)
  const setSidebarOpen = useAppStore((state) => state.setSidebarOpen)
  const darkMode = useAppStore((state) => state.darkMode)
  const toggleDarkMode = useAppStore((state) => state.toggleDarkMode)
  const setSettingsOpen = useAppStore((state) => state.setSettingsOpen)
  const setContextOpen = useAppStore((state) => state.setContextOpen)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const settingsButtonRef = useRef<HTMLButtonElement>(null)
  const contextButtonRef = useRef<HTMLButtonElement>(null)
  const { sourcesQuery, lookupQuery } = useWorkspaceLookup(searchWord)
  const sources = sourcesQuery.data ?? []

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  useEffect(() => {
    const shortcuts = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        window.dispatchEvent(new CustomEvent('mdict-focus-search'))
      }
      if ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === 'd') {
        event.preventDefault()
        toggleDarkMode()
      }
    }
    window.addEventListener('keydown', shortcuts)
    return () => window.removeEventListener('keydown', shortcuts)
  }, [toggleDarkMode])

  return (
    <div className="app-shell">
      <SourceLedger
        sources={sources}
        lookup={lookupQuery.data}
        loading={sourcesQuery.isLoading || lookupQuery.isLoading}
        returnFocusRef={menuButtonRef}
      />
      <div className="workspace-column">
        <header className="topbar">
          <button ref={menuButtonRef} className="icon-button mobile-menu" aria-label="Open source navigation" onClick={() => setSidebarOpen(true)}>
            <Menu size={19} />
          </button>
          <SearchBar />
          <nav className="topbar-actions" aria-label="Workspace actions">
            <button className="topbar-text-button" aria-label="Open saved words" onClick={() => window.dispatchEvent(new CustomEvent('mdict-open-saved'))}>
              <Bookmark size={15} /> <span>Saved</span>
            </button>
            <button ref={contextButtonRef} className="topbar-text-button" aria-label="Open context" onClick={() => setContextOpen(true)}>
              <MessageSquareText size={15} /> <span>Context</span>
            </button>
            <button className="icon-button" aria-label={darkMode ? 'Use light workspace' : 'Use dark workspace'} onClick={toggleDarkMode}>
              {darkMode ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button ref={settingsButtonRef} className="icon-button" aria-label="Open settings" onClick={() => setSettingsOpen(true)}>
              <Settings size={17} />
            </button>
          </nav>
        </header>
        <main className="workspace-main">
          <ReadingWorkspace
            query={searchWord}
            sources={sources}
            lookup={lookupQuery.data}
            loading={sourcesQuery.isLoading || lookupQuery.isLoading}
            error={(sourcesQuery.error ?? lookupQuery.error) as Error | null}
            onRefresh={() => {
              void sourcesQuery.refetch()
              void lookupQuery.refetch()
            }}
          />
        </main>
      </div>
      <ContextDrawer lookup={lookupQuery.data} returnFocusRef={contextButtonRef} />
      <SettingsPanel sources={sources} returnFocusRef={settingsButtonRef} />
    </div>
  )
}
