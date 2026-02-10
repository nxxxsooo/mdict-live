import { useWordMeta } from '@/hooks/useDict'

export function WordMeta({ word }: { word: string }) {
  const { data: meta } = useWordMeta(word)

  if (!meta?.found) return null

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm mt-2">
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
