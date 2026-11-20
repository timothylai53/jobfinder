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
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {lead && <p className="mt-1 text-[15px] text-muted-foreground">{lead}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

const MARK = {
  met: { Icon: CircleCheck, cls: 'text-primary' },
  partial: { Icon: TriangleAlert, cls: 'text-attention' },
  not_met: { Icon: CircleX, cls: 'text-red-700' },
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

/** rough: the job was saved from a search card only, so the score is an estimate (dashed outline, ~). */
export function ScoreBadge({ score, gated, rough, size = 'md' }: { score: number | null; gated?: boolean; rough?: boolean; size?: 'md' | 'lg' }) {
  return (
    <span
      className={cn('inline-flex justify-center font-semibold tabular-nums', scoreTone(score, gated),
        size === 'lg' ? 'min-w-20 rounded-xl px-3 py-2 text-4xl leading-none tracking-tight' : 'min-w-11 rounded-md px-1.5 py-0.5 text-sm',
        rough && 'border border-dashed border-current opacity-80')}
      title={rough ? 'Rough score (summary only): paste the full JD for a real score' : gated ? 'A hard gate failed (score capped)' : undefined}
    >
      {rough && score !== null ? '~' : ''}
      {score ?? '–'}
      {gated && <span className="sr-only"> (hard requirement failed)</span>}
    </span>
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
}: {
  value: string
  onChange: (v: string) => void
  options: (string | { value: string; label: string })[]
  className?: string
}) {
  return (
    <select
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
  return <p className="text-sm text-red-600">{error instanceof Error ? error.message : String(error)}</p>
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'ok' | 'warn' }) {
  const cls = { info: 'bg-blue-50 text-blue-900', ok: 'bg-green-50 text-green-900', warn: 'bg-amber-50 text-amber-900' }[tone]
  return <div className={cn('rounded-md px-3 py-2 text-sm', cls)}>{children}</div>
}
