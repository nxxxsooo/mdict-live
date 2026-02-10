import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/dict'
import { useAppStore } from '@/stores/useAppStore'

export function useDicts() {
  return useQuery({
    queryKey: ['dicts'],
    queryFn: api.getDicts,
    staleTime: 60_000,
  })
}

export function useLookup(word: string) {
  const activeDict = useAppStore((s) => s.activeDict)

  return useQuery({
    queryKey: ['lookup', word, activeDict],
    queryFn: () =>
      activeDict === 'all'
        ? api.lookupAll(word)
        : api.lookupWord(activeDict, word).then((r) => ({
            word: r.word,
            results: r.found ? [r] : [],
            total: r.found ? 1 : 0,
          })),
    enabled: !!word.trim(),
    staleTime: 5 * 60_000,
  })
}

export function useSuggest(query: string) {
  return useQuery({
    queryKey: ['suggest', query],
    queryFn: () => api.suggest(query),
    enabled: query.trim().length >= 1,
    staleTime: 30_000,
  })
}

export function useHistory() {
  return useQuery({
    queryKey: ['history'],
    queryFn: () => api.getHistory(),
    staleTime: 10_000,
  })
}

export function useWordMeta(word: string) {
  return useQuery({
    queryKey: ['meta', word],
    queryFn: () => api.getWordMeta(word),
    enabled: !!word.trim(),
    staleTime: 5 * 60_000,
  })
}

export function useToggleDict() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.toggleDict,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dicts'] })
    },
  })
}

export function useClearHistory() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.clearHistory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

// Wordbook hooks

export function useWordbooks() {
  return useQuery({
    queryKey: ['wordbooks'],
    queryFn: api.getWordbooks,
  })
}

export function useCreateWordbook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.createWordbook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wordbooks'] })
    },
  })
}

export function useDeleteWordbook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deleteWordbook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wordbooks'] })
    },
  })
}

export function useUpdateWordbook() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      api.updateWordbook(id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wordbooks'] })
    },
  })
}

export function useWordbookEntries(wbId: number) {
  return useQuery({
    queryKey: ['wordbook', wbId, 'entries'],
    queryFn: () => api.getWordbookEntries(wbId),
    enabled: !!wbId,
  })
}

export function useAddWordbookEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ wbId, word }: { wbId: number; word: string }) =>
      api.addWordbookEntry(wbId, word),
    onSuccess: (_, { wbId }) => {
      queryClient.invalidateQueries({ queryKey: ['wordbook', wbId, 'entries'] })
      queryClient.invalidateQueries({ queryKey: ['checkWord'] })
    },
  })
}

export function useDeleteWordbookEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ wbId, entryId }: { wbId: number; entryId: number }) =>
      api.deleteWordbookEntry(wbId, entryId),
    onSuccess: (_, { wbId }) => {
      queryClient.invalidateQueries({ queryKey: ['wordbook', wbId, 'entries'] })
      queryClient.invalidateQueries({ queryKey: ['checkWord'] })
    },
  })
}

export function useCheckWordInWordbooks(word: string) {
  return useQuery({
    queryKey: ['checkWord', word],
    queryFn: () => api.checkWordInWordbooks(word),
    enabled: !!word,
  })
}
