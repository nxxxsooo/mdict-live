import { X, Moon, Sun } from 'lucide-react'
import { useAppStore } from '@/stores/useAppStore'
import { useDicts, useToggleDict } from '@/hooks/useDict'

export function SettingsPanel() {
  const isOpen = useAppStore((s) => s.settingsOpen)
  const setOpen = useAppStore((s) => s.setSettingsOpen)
  const darkMode = useAppStore((s) => s.darkMode)
  const toggleDarkMode = useAppStore((s) => s.toggleDarkMode)

  const { data: dicts = [] } = useDicts()
  const toggleDict = useToggleDict()
  const realDicts = dicts.filter((d) => d.type !== 'app')

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 transition-opacity"
          onClick={() => setOpen(false)}
        />
      )}
      <div
        className={`fixed top-0 right-0 z-50 h-screen w-80 bg-white dark:bg-slate-900 border-l border-gray-200 dark:border-slate-800 shadow-xl transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-slate-800">
          <h2 className="font-semibold text-lg text-slate-800 dark:text-slate-100">Settings</h2>
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-500 dark:text-slate-400 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-4 space-y-6">
          {/* Appearance */}
          <section>
            <h3 className="text-sm font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-3">
              Appearance
            </h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-700 dark:text-slate-200">
                {darkMode ? <Moon size={18} /> : <Sun size={18} />}
                <span>Dark Mode</span>
              </div>
              <button
                onClick={toggleDarkMode}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  darkMode ? 'bg-blue-600' : 'bg-gray-200 dark:bg-slate-700'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    darkMode ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-400 dark:text-slate-500">
              Switch between light and dark themes. (Shortcut: Ctrl+Shift+D)
            </p>
          </section>

          {/* Dictionaries */}
          <section>
            <h3 className="text-sm font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-3">
              Dictionaries
            </h3>
            <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto pr-1">
              {realDicts.map((dict) => (
                <div key={dict.uuid} className="flex items-center justify-between">
                  <div className="flex items-center gap-2 truncate pr-2 min-w-0">
                    <img
                      src={dict.logo}
                      alt=""
                      className="w-4 h-4 rounded flex-shrink-0"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                    />
                    <span
                      className={`text-sm truncate transition-colors ${
                        dict.enabled ? 'text-gray-900 dark:text-slate-200' : 'text-gray-400 dark:text-slate-500'
                      }`}
                      title={dict.title}
                    >
                      {dict.title}
                    </span>
                  </div>
                  <button
                    onClick={() => toggleDict.mutate(dict.uuid)}
                    className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors ${
                      dict.enabled ? 'bg-blue-500' : 'bg-gray-300 dark:bg-slate-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
                        dict.enabled ? 'translate-x-4.5' : 'translate-x-0.5'
                      }`}
                    />
                  </button>
                </div>
              ))}
              {realDicts.length === 0 && (
                <div className="text-sm text-gray-400 dark:text-slate-500 text-center py-4">
                  No dictionaries found
                </div>
              )}
            </div>
          </section>

          {/* About */}
          <section>
            <h3 className="text-sm font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-3">
              About
            </h3>
            <div className="text-sm text-gray-600 dark:text-slate-300">
              <p className="font-medium">Flask MDict</p>
              <p className="text-xs text-gray-400 mt-1">React SPA Refinement</p>
            </div>
          </section>
        </div>
      </div>
    </>
  )
}
