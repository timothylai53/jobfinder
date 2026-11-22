import type { SourceRow } from '@/api/types'
import { formatDateTime } from '@/lib/score'

export function sourceStatus(s: SourceRow): { text: string; tone: string } {
  if (s.running) return { text: 'Fetching now…', tone: 'text-attention' }
  if (!s.enabled) return { text: 'Off', tone: 'text-muted-foreground' }
  if (s.status === 'paused') return { text: `Paused until ${formatDateTime(s.paused_until)}`, tone: 'text-danger' }
  if (s.status === 'error') return { text: 'Last run failed', tone: 'text-attention' }
  if (s.runs_today >= s.max_runs_per_day) return { text: 'Daily limit reached', tone: 'text-muted-foreground' }
  return { text: 'Ready', tone: 'text-foreground' }
}
