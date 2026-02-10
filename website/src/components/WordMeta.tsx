import { Heart } from 'lucide-react'
import {
  useWordMeta,
  useCheckWordInWordbooks,
  useWordbooks,
  useAddWordbookEntry,
  useDeleteWordbookEntry,
  useCreateWordbook,
  useWordbookEntries,
} from '@/hooks/useDict'

export function WordMeta({ word }: { word: string }) {
  const { data: meta } = useWordMeta(word)
  const { data: savedEntries = [] } = useCheckWordInWordbooks(word)
  const { data: wordbooks = [] } = useWordbooks()

  const createWordbook = useCreateWordbook()
  const addEntry = useAddWordbookEntry()
  const deleteEntry = useDeleteWordbookEntry()

  const isSaved = savedEntries.length > 0

  const handleToggle = async () => {
    if (isSaved) {
      // Remove from ALL wordbooks containing this word
      for (const entry of savedEntries) {
        deleteEntry.mutate({ wbId: entry.wordbook_id, entryId: entry.id })
      }
    } else {
      let targetWbId
      if (wordbooks.length === 0) {
        // Create default wordbook
        const newWb = await createWordbook.mutateAsync('My Words')
        targetWbId = newWb.id
      } else {
        // Use first wordbook (MVP)
        targetWbId = wordbooks[0].id
      }
      if (targetWbId) {
        addEntry.mutate({ wbId: targetWbId, word })
      }
    }
  }

  if (!meta?.found) return null

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm mt-2">
      <button
        onClick={handleToggle}
        className={`p-1 rounded-full transition-colors ${
          isSaved
            ? 'text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20'
            : 'text-gray-400 hover:text-red-500 hover:bg-gray-100 dark:hover:bg-slate-800'
        }`}
        title={isSaved ? 'Remove from wordbook' : 'Add to wordbook'}
      >
        <Heart size={18} fill={isSaved ? 'currentColor' : 'none'} />
      </button>
      {meta.phonetic && (
        <span className="text-gray-500 dark:text-slate-400">/{meta.phonetic}/</span>
      )}
      {meta.oxford && (
        <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 rounded text-xs font-medium">
          Oxford 3000
        </span>
      )}
      {meta.collins && meta.collins > 0 && (
        <span className="text-yellow-500" title={`Collins ${meta.collins} star`}>
          {'★'.repeat(meta.collins)}{'☆'.repeat(Math.max(0, 5 - meta.collins))}
        </span>
      )}
      {meta.tags?.map((tag) => (
        <span
          key={tag}
          className="px-1.5 py-0.5 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 rounded text-xs font-medium"
        >
          {tag.toUpperCase()}
        </span>
      ))}
      {meta.bnc && (
        <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300 rounded text-xs">
          BNC: {meta.bnc}
        </span>
      )}
      {meta.frq && (
        <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-slate-800 text-gray-600 dark:text-slate-300 rounded text-xs">
          COCA: {meta.frq}
        </span>
      )}
    </div>
  )
}
