import { useQuery } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { ProfileStatus } from '@/api/types'
import { formatMonth } from '@/lib/score'

export function useProfileStatus() {
  // Key starts with 'profile' so every profile / bank change that invalidates ['profile'] refreshes it.
  return useQuery({
    queryKey: ['profile', 'status'],
    queryFn: () => api.get<ProfileStatus>('/api/profile/status'),
    refetchOnMount: 'always',
  })
}

export function educationLabel(e: ProfileStatus['education']): string {
  if (!e) return 'none found'
  const parts = [e.level + (e.field ? ` in ${e.field}` : '')]
  if (e.in_progress) parts.push(`in progress${e.expected ? `, expected ${formatMonth(e.expected)}` : ''}`)
  parts.push(e.source === 'profile' ? 'from your profile' : `from ${e.source}`)
  return parts.join(', ')
}
