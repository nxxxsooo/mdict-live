import { useState } from 'react'
import { History, ChevronDown, ChevronUp, Trash2 } from 'lucide-react'
import { useHistory, useClearHistory } from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'

export function HistoryPanel() {
  const [expanded, setExpanded] = useState(false)
  const { data: history = [] } = useHistory()
  const clearHistory = useClearHistory()
  const setSearchWord = useAppStore((s) => s.setSearchWord)

  if (history.length === 0) return null

  const shown = expanded ? history : history.slice(0, 10)

  return (
    <div className="mt-4 bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-800 shadow-sm transition-colors">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <History size={16} className="text-gray-400" />
          <span className="text-sm font-medium text-gray-600 dark:text-slate-300">Recent Searches</span>
          <span className="text-xs text-gray-400">({history.length})</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => clearHistory.mutate()}
            className="p-1 text-gray-400 hover:text-red-500 rounded hover:bg-gray-50 dark:hover:bg-slate-800"
            title="Clear history"
          >
            <Trash2 size={14} />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-slate-300 rounded hover:bg-gray-50 dark:hover:bg-slate-800"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5 p-3">
        {shown.map((item) => (
          <button
            key={item.word}
            onClick={() => setSearchWord(item.word)}
            className="px-2.5 py-1 text-sm text-gray-600 dark:text-slate-400 bg-gray-50 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-600 dark:hover:text-blue-400 rounded-lg transition-colors"
          >
            {item.word}
          </button>
        ))}
        {!expanded && history.length > 10 && (
          <button
            onClick={() => setExpanded(true)}
            className="px-2.5 py-1 text-sm text-blue-500 hover:text-blue-600 dark:hover:text-blue-400"
          >
            +{history.length - 10} more
          </button>
        )}
      </div>
    </div>
  )
}
