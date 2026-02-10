import { useState, useRef, useEffect, useCallback } from 'react'
import { Search, X } from 'lucide-react'
import { useSuggest } from '@/hooks/useDict'
import { useAppStore } from '@/stores/useAppStore'

export function SearchBar() {
  const [input, setInput] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  const setSearchWord = useAppStore((s) => s.setSearchWord)
  const searchWord = useAppStore((s) => s.searchWord)

  // Debounced query for suggestions
  const [debouncedQuery, setDebouncedQuery] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(input), 300)
    return () => clearTimeout(timer)
  }, [input])

  const { data: suggestions = [] } = useSuggest(debouncedQuery)

  // Sync input when searchWord changes externally (e.g. from history click)
  useEffect(() => {
    if (searchWord && searchWord !== input) {
      setInput(searchWord)
    }
  }, [searchWord]) // eslint-disable-line react-hooks/exhaustive-deps

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const doSearch = useCallback(
    (word: string) => {
      const trimmed = word.trim()
      if (trimmed) {
        setSearchWord(trimmed)
        setInput(trimmed)
        setShowSuggestions(false)
        inputRef.current?.blur()
      }
    },
    [setSearchWord],
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx((prev) => Math.min(prev + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx((prev) => Math.max(prev - 1, -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectedIdx >= 0 && suggestions[selectedIdx]) {
        doSearch(suggestions[selectedIdx])
      } else {
        doSearch(input)
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  return (
    <div ref={wrapperRef} className="relative w-full max-w-2xl mx-auto">
      <div className="flex items-center bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-sm focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 dark:focus-within:ring-blue-900/30 transition-all">
        <Search className="ml-4 text-gray-400" size={20} />
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => {
            setInput(e.target.value)
            setShowSuggestions(true)
            setSelectedIdx(-1)
          }}
          onFocus={() => input.trim() && setShowSuggestions(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search a word..."
          className="flex-1 px-3 py-3 text-lg bg-transparent outline-none text-slate-900 dark:text-slate-100 placeholder-gray-400"
          autoComplete="off"
          spellCheck={false}
        />
        {input && (
          <button
            onClick={() => {
              setInput('')
              setShowSuggestions(false)
              inputRef.current?.focus()
            }}
            className="mr-2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-slate-200 rounded-full hover:bg-gray-100 dark:hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        )}
        <button
          onClick={() => doSearch(input)}
          className="mr-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
        >
          Search
        </button>
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <ul className="absolute z-50 w-full mt-1 bg-white dark:bg-slate-900 border border-gray-200 dark:border-slate-700 rounded-xl shadow-lg max-h-64 overflow-y-auto">
          {suggestions.map((s, i) => (
            <li
              key={s}
              onMouseDown={() => doSearch(s)}
              className={`px-4 py-2 cursor-pointer text-sm ${
                i === selectedIdx
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                  : 'hover:bg-gray-50 dark:hover:bg-slate-800 text-gray-700 dark:text-slate-300'
              }`}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
