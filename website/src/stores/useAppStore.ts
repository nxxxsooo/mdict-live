import { create } from 'zustand'

interface AppState {
  searchWord: string
  activeDict: string // 'all' or a specific uuid
  sidebarOpen: boolean
  setSearchWord: (word: string) => void
  setActiveDict: (uuid: string) => void
  setSidebarOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  searchWord: '',
  activeDict: 'all',
  sidebarOpen: false,
  setSearchWord: (word) => set({ searchWord: word }),
  setActiveDict: (uuid) => set({ activeDict: uuid }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))
