import type { ItemStatus } from '@/api/types'

export const STATUS_ICON: Record<ItemStatus, string> = {
  met: '✅',
  partial: '⚠️',
  not_met: '❌',
  not_specified: '➖',
}

export const STATUS_LABEL: Record<ItemStatus, string> = {
  met: 'met',
  partial: 'partial',
  not_met: 'not met',
  not_specified: 'not specified',
}

/** Tailwind classes for a 0-100 score badge; gated jobs are always red. */
export function scoreTone(score: number | null, gated = false): string {
  if (score === null) return 'bg-muted text-muted-foreground'
  if (gated) return 'bg-red-100 text-red-800'
  if (score >= 70) return 'bg-green-100 text-green-800'
  if (score >= 50) return 'bg-amber-100 text-amber-800'
  return 'bg-red-100 text-red-800'
}

export function formatSalary(min: number | null, max: number | null, currency: string): string {
  if (min === null && max === null) return ''
  const c = currency || 'RM'
  const f = (n: number) => n.toLocaleString('en-MY', { maximumFractionDigits: 0 })
  if (min !== null && max !== null && min !== max) return `${c} ${f(min)}–${f(max)}`
  return `${c} ${f((min ?? max) as number)}`
}

/** Split "a, b,, c" into ["a", "b", "c"], de-duplicated, order kept. */
export function parseList(text: string): string[] {
  const out: string[] = []
  for (const part of text.split(/[,\n]/)) {
    const t = part.trim()
    if (t && !out.some((o) => o.toLowerCase() === t.toLowerCase())) out.push(t)
  }
  return out
}

export type SortKey = 'score' | 'fetched_at' | 'posted_date' | 'title' | 'company'

interface Sortable {
  score: number | null
  fetched_at: string
  posted_date: string | null
  title: string
  company: string
}

/** Sort copy; nulls always last regardless of direction. */
export function sortJobs<T extends Sortable>(jobs: T[], key: SortKey, desc: boolean): T[] {
  return [...jobs].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return desc ? -cmp : cmp
  })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return d.toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric' })
}
