import type { ItemStatus } from '@/api/types'

export const STATUS_LABEL: Record<ItemStatus, string> = {
  met: 'met',
  partial: 'partial',
  not_met: 'not met',
  not_specified: 'not specified',
}

/** Tailwind colour classes for a 0-100 score badge (the tab's fill, text and 2px base line). The accent marks good
 * matches; amber a partial one; weak scores stay neutral, and only a failed hard gate is red. */
export function scoreTone(score: number | null, gated = false): string {
  if (score === null) return 'bg-muted text-muted-foreground border-border'
  if (gated) return 'bg-danger-bg text-danger border-danger'
  if (score >= 70) return 'bg-accent text-accent-foreground border-primary'
  if (score >= 50) return 'bg-attention-bg text-attention border-attention'
  return 'bg-score-weak text-foreground border-foreground/45'
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

// One date format everywhere: "15 Nov 2026" (en-GB order, regardless of the browser's own locale).
const DATE = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
const TIME = new Intl.DateTimeFormat('en-GB', { hour: 'numeric', minute: '2-digit', hour12: true })
const MONTH = new Intl.DateTimeFormat('en-GB', { month: 'short', year: 'numeric' })

function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return Number.isNaN(d.getTime()) ? null : d
}

/** "15 Nov 2026" */
export function formatDate(iso: string | null | undefined): string {
  const d = toDate(iso)
  return d ? DATE.format(d).replace('Sept', 'Sep') : ''
}

/** "15 Nov 2026, 10:48 pm" for moments (status changes, runs, notifications). */
export function formatDateTime(iso: string | null | undefined): string {
  const d = toDate(iso)
  return d ? `${formatDate(iso)}, ${TIME.format(d).replace(/\s?([ap])\.?m\.?$/i, ' $1m').toLowerCase()}` : ''
}

const DAY_MONTH = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short' })

/** "13 Nov, 11:10 am" for log rows; the year is added only when it isn't this year. */
export function formatShortDateTime(iso: string | null | undefined, now = new Date()): string {
  const d = toDate(iso)
  if (!d) return ''
  const day = d.getFullYear() === now.getFullYear() ? DAY_MONTH.format(d).replace('Sept', 'Sep') : formatDate(iso)
  return `${day}, ${TIME.format(d).replace(/\s?([ap])\.?m\.?$/i, ' $1m').toLowerCase()}`
}

/** "Nov 2026" for months (expected graduation). */
export function formatMonth(iso: string | null | undefined): string {
  const d = toDate(iso)
  return d ? MONTH.format(d).replace('Sept', 'Sep') : ''
}

/** "Jun 2025 – Sep 2025", "2024" (not "2024 – 2024"), or just the one date that is set. */
export function dateRange(start: string, end: string): string {
  const s = start.trim()
  const e = end.trim()
  const norm = (x: string) => x.toLowerCase().split(/\s+/).join(' ')
  if (s && e && norm(s) === norm(e)) return s
  return [s, e].filter(Boolean).join(' – ')
}
