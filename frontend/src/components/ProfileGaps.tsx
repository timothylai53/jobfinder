import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'
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

/** Amber banner listing key profile fields that are missing, each linking to where it is fixed. */
export default function ProfileGaps({ context = 'scores' }: { context?: 'scores' | 'score' }) {
  const q = useProfileStatus()
  const missing = q.data?.missing ?? []
  if (missing.length === 0) return null
  return (
    <div role="status" className="flex gap-3 rounded-lg border border-attention-edge bg-attention-bg px-4 py-3 text-attention">
      <AlertTriangle className="mt-0.5 size-5 shrink-0" />
      <div className="text-[15px]">
        <p className="font-semibold">
          {context === 'score' ? 'This score may be off.' : 'Scores may be off.'} Your profile is missing{' '}
          {missing.map((m) => m.label).join(', ').replace(/, ([^,]*)$/, ' and $1')}.
        </p>
        <ul className="mt-1 flex flex-col gap-0.5 text-sm">
          {missing.map((m) => (
            <li key={m.key}>
              <Link to={m.fix} className="font-medium underline">Add {m.label}</Link>
              <span className="text-attention/80">: {m.hint}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
