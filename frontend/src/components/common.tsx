import { CircleCheck, CircleMinus, CircleX, TriangleAlert } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import type { ItemStatus } from '@/api/types'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { parseList, scoreTone, STATUS_LABEL } from '@/lib/score'

export function PageHeader({ title, lead, children }: { title: string; lead?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[28px] leading-tight font-semibold">{title}</h1>
        {lead && <p className="mt-1 text-[15px] text-muted-foreground">{lead}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

const MARK = {
  met: { Icon: CircleCheck, cls: 'text-primary' },
  partial: { Icon: TriangleAlert, cls: 'text-attention' },
  not_met: { Icon: CircleX, cls: 'text-danger' },
  not_specified: { Icon: CircleMinus, cls: 'text-muted-foreground' },
} as const

/** The small warning icon in front of a fabrication-guard flag (decorative: the message says what is wrong). */
export function FlagIcon() {
  return <TriangleAlert aria-hidden className="mr-1 inline size-3.5 align-[-2px]" />
}

/** Met / partial / not met / not specified as a drawn icon with an accessible name (no emoji). */
export function StatusMark({ status, className }: { status: ItemStatus; className?: string }) {
  const { Icon, cls } = MARK[status]
  return <Icon role="img" aria-label={STATUS_LABEL[status]} className={cn('size-4 shrink-0', cls, className)} />
}

/** The score badge: a small index-card tab (rounded top, flat 2px base line in the score's colour), the same shape
 * everywhere. rough: the job was saved from a search card only, so the score is an estimate (dashed base line, ~). */
export function ScoreBadge({ score, gated, rough, size = 'md' }: { score: number | null; gated?: boolean; rough?: boolean; size?: 'md' | 'lg' }) {
  return (
    <span
      className={cn('inline-flex justify-center rounded-t-md rounded-b-none border-b-2 font-heading font-semibold tabular-nums',
        scoreTone(score, gated),
        size === 'lg' ? 'min-w-20 rounded-t-lg px-3 pt-2.5 pb-2 text-4xl leading-none tracking-tight' : 'min-w-11 px-1.5 pt-0.5 text-sm',
        rough && 'border-dashed')}
      title={rough ? 'Rough score (summary only): paste the full JD for a real score' : gated ? 'A hard gate failed (score capped)' : undefined}
    >
      {rough && score !== null ? '~' : ''}
      {score ?? '–'}
      {gated && <span className="sr-only"> (hard requirement failed)</span>}
    </span>
  )
}

/** The JobFinder mark: an index card with a green tab and two ruled lines. Drawn on a 32-unit grid with 2.4-unit
 * strokes so it still reads at 16 px (the favicon is the same drawing). */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn('size-6 shrink-0', className)}>
      <path d="M19 6h7a2 2 0 0 1 2 2v1H19z" fill="var(--primary)" />
      <rect x="4" y="9" width="24" height="17" rx="2.5" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <path d="M9 16h14M9 21h9" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

export function Field({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    // A wrapping <label> ties the caption to its input (click target + accessible name).
    <label className={cn('flex flex-col gap-1', className)}>
      <span className="text-sm font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

/** Comma-separated text box bound to a string[]; commits on blur so typing commas is easy. */
export function ListInput({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [text, setText] = useState(value.join(', '))
  // Follow outside changes (a reload after saving), but not the echo of our own typing, which would eat ", ".
  useEffect(() => {
    setText((t) => (parseList(t).join('|') === value.join('|') ? t : value.join(', ')))
  }, [value])
  return (
    <Input
      value={text}
      placeholder={placeholder}
      onChange={(e) => { setText(e.target.value); onChange(parseList(e.target.value)) }}
      onBlur={() => setText(parseList(text).join(', '))}
    />
  )
}

export function NativeSelect({
  value,
  onChange,
  options,
  className,
  label,
}: {
  value: string
  onChange: (v: string) => void
  options: (string | { value: string; label: string })[]
  className?: string
  /** Accessible name when there is no visible <label> around it. */
  label?: string
}) {
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn('h-9 rounded-lg border border-input bg-background px-2 text-[15px]', className)}
    >
      {options.map((o) => {
        const opt = typeof o === 'string' ? { value: o, label: o } : o
        return (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        )
      })}
    </select>
  )
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null
  return <p className="text-sm text-danger">{error instanceof Error ? error.message : String(error)}</p>
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'ok' | 'warn' }) {
  const cls = { info: 'border bg-background', ok: 'border bg-background', warn: 'border border-attention-edge/50 bg-attention-bg text-attention' }[tone]
  return <div className={cn('rounded-md px-3.5 py-2.5 text-sm', cls)}>{children}</div>
}
