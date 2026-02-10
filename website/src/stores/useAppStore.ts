import { create } from 'zustand'

const SIDEBAR_WIDTH_KEY = 'sidebarWidth'
const DEFAULT_SIDEBAR_WIDTH = 256
const MIN_SIDEBAR_WIDTH = 200
const MAX_SIDEBAR_WIDTH = 500

function loadSidebarWidth(): number {
  try {
    const saved = localStorage.getItem(SIDEBAR_WIDTH_KEY)
    if (saved) {
      const w = Number(saved)
      if (w >= MIN_SIDEBAR_WIDTH && w <= MAX_SIDEBAR_WIDTH) return w
    }
  } catch {}
  return DEFAULT_SIDEBAR_WIDTH
}

interface AppState {
  searchWord: string
  activeDict: string // 'all' or a specific uuid
  sidebarOpen: boolean
  sidebarWidth: number
  setSearchWord: (word: string) => void
  setActiveDict: (uuid: string) => void
  setSidebarOpen: (open: boolean) => void
  setSidebarWidth: (width: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  searchWord: '',
  activeDict: 'all',
  sidebarOpen: false,
  sidebarWidth: loadSidebarWidth(),
  setSearchWord: (word) => set({ searchWord: word }),
  setActiveDict: (uuid) => set({ activeDict: uuid }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSidebarWidth: (width) => {
    const clamped = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width))
    try { localStorage.setItem(SIDEBAR_WIDTH_KEY, String(clamped)) } catch {}
    set({ sidebarWidth: clamped })
  },
}))

export { MIN_SIDEBAR_WIDTH, MAX_SIDEBAR_WIDTH }
