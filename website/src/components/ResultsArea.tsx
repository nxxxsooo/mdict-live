import { useLookup } from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'
import { DictPanel } from './DictPanel'
import { BookOpen } from 'lucide-react'

export function ResultsArea() {
  const searchWord = useAppStore((s) => s.searchWord)
  const { data, isLoading, error } = useLookup(searchWord)

  if (!searchWord) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-400">
        <BookOpen size={48} strokeWidth={1} />
        <p className="mt-4 text-lg">Type a word to search</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4 mt-4">
        {[1, 2].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 overflow-hidden animate-pulse">
            <div className="h-10 bg-gray-50 border-b border-gray-100" />
            <div className="p-4 space-y-3">
              <div className="h-4 bg-gray-100 rounded w-3/4" />
              <div className="h-4 bg-gray-100 rounded w-1/2" />
              <div className="h-4 bg-gray-100 rounded w-2/3" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
        Failed to look up word. Please try again.
      </div>
    )
  }

  const results = data?.results ?? []

  if (results.length === 0) {
    return (
      <div className="mt-4 p-8 text-center text-gray-400">
        <p className="text-lg">No results found for "<span className="text-gray-600 font-medium">{searchWord}</span>"</p>
      </div>
    )
  }

  return (
    <div className="mt-4 space-y-4">
      {results.map((r) => (
        <DictPanel
          key={r.uuid}
          uuid={r.uuid}
          title={r.title ?? 'Dictionary'}
          logo={r.logo}
          html={r.html}
        />
      ))}
    </div>
  )
}
