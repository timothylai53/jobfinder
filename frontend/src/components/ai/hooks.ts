import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { AiSettings, AiTaskType, DocumentRow } from '@/api/types'

export function useAiSettings() {
  return useQuery({ queryKey: ['ai-settings'], queryFn: () => api.get<AiSettings>('/api/ai/settings') })
}

export function useDocuments(jobId: number) {
  return useQuery({ queryKey: ['documents', jobId], queryFn: () => api.get<DocumentRow[]>(`/api/jobs/${jobId}/documents`) })
}

export type AiOpen = AiTaskType | 'template' | null

/** Which AI dialog is open on Job Detail. `n` makes every opening a fresh task. */
export function useAiDialog() {
  const [state, setState] = useState<{ open: AiOpen; n: number }>({ open: null, n: 0 })
  return {
    ...state,
    start: (open: AiOpen) => setState((s) => ({ open, n: s.n + 1 })),
    close: () => setState((s) => ({ ...s, open: null })),
  }
}
