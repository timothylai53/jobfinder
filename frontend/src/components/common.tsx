import { useEffect, useState, type ReactNode } from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { parseList, scoreTone } from '@/lib/score'

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
      <h1 className="text-xl font-semibold">{title}</h1>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

/** rough: the job was saved from a search card only, so the score is an estimate (dashed outline, ~). */
export function ScoreBadge({ score, gated, rough }: { score: number | null; gated?: boolean; rough?: boolean }) {
  return (
    <span
      className={cn('inline-flex min-w-11 justify-center rounded-md px-1.5 py-0.5 text-sm font-semibold tabular-nums', scoreTone(score, gated),
        rough && 'border border-dashed border-current opacity-80')}
      title={rough ? 'Rough score (summary only): paste the full JD for a real score' : gated ? 'A hard gate failed (score capped)' : undefined}
    >
      {rough && score !== null ? '~' : ''}
      {score ?? '–'}
      {gated ? ' ❌' : ''}
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
  useEffect(() => setText(value.join(', ')), [value])
  return (
    <Input
      value={text}
      placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => onChange(parseList(text))}
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
      className={cn('h-8 rounded-lg border border-input bg-background px-2 text-[15px]', className)}
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
