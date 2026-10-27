import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Clock3, Search, X } from 'lucide-react'
import { useHistory } from '@/hooks/useDict'
import { useWorkspaceSuggestions } from '@/hooks/useWorkspace'
import { useAppStore } from '@/stores/useAppStore'

export function SearchBar() {
  const [input, setInput] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const listboxId = useId()
  const searchWord = useAppStore((state) => state.searchWord)
  const setSearchWord = useAppStore((state) => state.setSearchWord)
  const { data: history = [] } = useHistory()
  const { data: suggestions = [] } = useWorkspaceSuggestions(debouncedQuery)
  const options = input.trim() ? suggestions : history.slice(0, 10).map((item) => item.word)

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(input.trim()), 220)
    return () => window.clearTimeout(timeout)
  }, [input])

  useEffect(() => {
    if (searchWord && searchWord !== input) setInput(searchWord)
  }, [searchWord]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const focusSearch = () => inputRef.current?.focus()
    window.addEventListener('mdict-focus-search', focusSearch)
    return () => window.removeEventListener('mdict-focus-search', focusSearch)
  }, [])

  useEffect(() => {
    const dismiss = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', dismiss)
    return () => document.removeEventListener('mousedown', dismiss)
  }, [])

  const search = useCallback(
    (value: string) => {
      const query = value.trim()
      if (!query) return
      setInput(query)
      setSearchWord(query)
      setOpen(false)
      setSelectedIndex(-1)
    },
    [setSearchWord],
  )

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setSelectedIndex((index) => Math.min(index + 1, options.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setSelectedIndex((index) => Math.max(index - 1, -1))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      search(selectedIndex >= 0 ? options[selectedIndex] : input)
    } else if (event.key === 'Escape') {
      setOpen(false)
      setSelectedIndex(-1)
    }
  }

  return (
    <div ref={wrapperRef} className="search-combobox">
      <div className="search-field">
        <Search size={18} aria-hidden="true" />
        <input
          ref={inputRef}
          value={input}
          onChange={(event) => {
            setInput(event.target.value)
            setSelectedIndex(-1)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          role="combobox"
          aria-expanded={open && options.length > 0}
          aria-controls={listboxId}
          aria-activedescendant={selectedIndex >= 0 ? `${listboxId}-${selectedIndex}` : undefined}
          aria-autocomplete="list"
          placeholder="Search a word or phrase"
          autoComplete="off"
          spellCheck={false}
        />
        {input && (
          <button
            className="icon-button compact"
            aria-label="Clear search"
            onClick={() => {
              setInput('')
              setOpen(false)
              inputRef.current?.focus()
            }}
          >
            <X size={16} />
          </button>
        )}
        <kbd>⌘ K</kbd>
        <button className="primary-button" onClick={() => search(input)}>
          Look up
        </button>
      </div>
      {open && options.length > 0 && (
        <ul id={listboxId} role="listbox" className="suggestion-menu">
          {!input.trim() && <li className="suggestion-label">Recent searches</li>}
          {options.map((option, index) => (
            <li
              id={`${listboxId}-${index}`}
              key={`${option}-${index}`}
              role="option"
              aria-selected={selectedIndex === index}
              className={selectedIndex === index ? 'is-selected' : ''}
              onMouseDown={(event) => {
                event.preventDefault()
                search(option)
              }}
            >
              {!input.trim() && <Clock3 size={14} aria-hidden="true" />}
              <span>{option}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
