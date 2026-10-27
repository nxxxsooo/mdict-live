import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getV2Token, workspaceApi } from '@/api/workspace'
import { useAppStore } from '@/stores/useAppStore'

function useTokenRevision(): number {
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const refresh = () => setRevision((value) => value + 1)
    window.addEventListener('mdict-token-changed', refresh)
    return () => window.removeEventListener('mdict-token-changed', refresh)
  }, [])
  return revision
}

export function useWorkspaceSources() {
  const tokenRevision = useTokenRevision()
  return useQuery({
    queryKey: ['workspace-sources', getV2Token() ? 'v2' : 'legacy', tokenRevision],
    queryFn: workspaceApi.getSources,
    staleTime: 60_000,
  })
}

export function useWorkspaceLookup(query: string) {
  const activeSource = useAppStore((state) => state.activeDict)
  const sourcesQuery = useWorkspaceSources()
  return {
    sourcesQuery,
    lookupQuery: useQuery({
      queryKey: [
        'workspace-lookup',
        query,
        activeSource,
        sourcesQuery.data?.map((source) => `${source.id}:${source.revision ?? 'legacy'}`).join('|'),
      ],
      queryFn: () => workspaceApi.lookup(query, sourcesQuery.data ?? [], activeSource),
      enabled: Boolean(query.trim()) && sourcesQuery.isSuccess,
      staleTime: 4 * 60_000,
    }),
  }
}

export function useWorkspaceSuggestions(query: string) {
  return useQuery({
    queryKey: ['workspace-suggestions', query, getV2Token() ? 'v2' : 'legacy'],
    queryFn: () => workspaceApi.suggestions(query),
    enabled: query.trim().length > 0,
    staleTime: 30_000,
  })
}

export function useWorkspaceMetadata(query: string) {
  return useQuery({
    queryKey: ['workspace-metadata', query, getV2Token() ? 'v2' : 'legacy'],
    queryFn: () => workspaceApi.metadata(query),
    enabled: Boolean(query.trim()),
    staleTime: 5 * 60_000,
  })
}

export function useUpdateWorkspaceSource() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, enabled }: { sourceId: string; enabled: boolean }) =>
      workspaceApi.updateSource(sourceId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-sources'] })
      queryClient.invalidateQueries({ queryKey: ['workspace-lookup'] })
    },
  })
}

export function useRefreshWorkspace() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: ['workspace-sources'] })
    queryClient.invalidateQueries({ queryKey: ['workspace-lookup'] })
    queryClient.invalidateQueries({ queryKey: ['workspace-metadata'] })
  }
}
