import { create } from 'zustand'

const SIDEBAR_WIDTH_KEY = 'sidebarWidth'
const DEFAULT_SIDEBAR_WIDTH = 256
const MIN_SIDEBAR_WIDTH = 200
const MAX_SIDEBAR_WIDTH = 500

function loadSidebarWidth(): number {
  if (typeof window === 'undefined') return DEFAULT_SIDEBAR_WIDTH
  try {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    if (saved) {
      const w = Number(saved)
      if (w >= MIN_SIDEBAR_WIDTH && w <= MAX_SIDEBAR_WIDTH) return w
    }
  } catch {}

  // Default to 30% width, clamped
  const width30 = window.innerWidth * 0.3
  return Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width30))
}

interface AppState {
  searchWord: string
  activeDict: string // 'all' or a specific uuid
  sidebarOpen: boolean
  sidebarWidth: number
  darkMode: boolean
  activeSidebarTab: 'dicts' | 'history' | 'wordbook'
  settingsOpen: boolean
  setSearchWord: (word: string) => void
  setActiveDict: (uuid: string) => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void
  toggleDarkMode: () => void
  setActiveSidebarTab: (tab: 'dicts' | 'history' | 'wordbook') => void
  setSettingsOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  searchWord: '',
  activeDict: 'all',
  sidebarOpen: false,
  sidebarWidth: loadSidebarWidth(),
  darkMode: localStorage.getItem('darkMode') === 'true',
  activeSidebarTab: 'dicts',
  settingsOpen: false,
  setSearchWord: (word) => set({ searchWord: word }),
  setActiveDict: (uuid) => set({ activeDict: uuid }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarWidth: (width) => {
    const clamped = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width))
    try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(clamped)) } catch {}
    set({ sidebarWidth: clamped })
  },
  toggleDarkMode: () => set((state) => {
    const next = !state.darkMode
    try { localStorage.setItem('darkMode', String(next)) } catch {}
    return { darkMode: next }
  }),
  setActiveSidebarTab: (tab) => set({ activeSidebarTab: tab }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
}))

export { MIN_SIDEBAR_WIDTH, MAX_SIDEBAR_WIDTH }
