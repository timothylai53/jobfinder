import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { AutomationRow, AutomationRunRow } from '@/api/types'
import { ErrorText, NativeSelect, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { formatDateTime, formatShortDateTime } from '@/lib/score'
import { lastRunSummary, runRows, STATUS_LABEL, type RowStatus, type RunLogRow } from '@/lib/runlog'
import { useLocalCopy } from '@/lib/hooks'

const RESULT_TONE: Record<string, string> = {
  ok: 'bg-selected text-foreground', error: 'bg-danger-bg text-danger',
  skipped: 'bg-muted text-muted-foreground', running: 'bg-attention-bg text-attention',
}

function when(iso: string | null | undefined) {
  return iso ? formatDateTime(iso) : '—'
}

/** One automation as a row: on/off with what it does, when it runs, how its last run went, and Run now. */
function AutomationItem({ a }: { a: AutomationRow }) {
  const qc = useQueryClient()
  const [time, setTime] = useLocalCopy(a.schedule)
  const update = useMutation({
    mutationFn: (body: Partial<AutomationRow>) => api.put(`/api/automations/${a.key}`, { enabled: a.enabled, mode: a.mode, schedule: a.schedule, ...body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['automations'] }),
  })
  const run = useMutation({
    mutationFn: () => api.post(`/api/automations/${a.key}/run`),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['automations'] }), 800)
      setTimeout(() => qc.invalidateQueries({ queryKey: ['automation-runs'] }), 800)
    },
  })
  const id = `auto-${a.key}`
  return (
    <li className="grid gap-x-6 gap-y-3 px-5 py-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1.1fr)_auto] lg:items-start">
      <div className="flex items-start gap-3">
        <input id={id} type="checkbox" className="mt-1 size-4 shrink-0 accent-foreground" checked={a.enabled}
          onChange={(e) => update.mutate({ enabled: e.target.checked })} />
        <label htmlFor={id} className="min-w-0">
          <span className={cn('font-medium', !a.enabled && 'text-muted-foreground')}>{a.label}</span>
          {!a.enabled && <span className="text-sm text-muted-foreground"> (off)</span>}
          <span className="block text-sm text-muted-foreground">{a.description}</span>
        </label>
      </div>
      <div className="flex flex-col gap-1.5">
        <span className="text-sm text-muted-foreground lg:sr-only">When</span>
        <div className="flex flex-wrap items-center gap-2">
          <NativeSelect label={`When ${a.label} runs`} value={a.mode} onChange={(v) => update.mutate({ mode: v as AutomationRow['mode'] })}
            options={[{ value: 'scheduled', label: a.daily ? 'Every day at' : 'Right after Fetch jobs' }, { value: 'manual', label: 'Only when I run it' }]} />
          {a.daily && a.mode === 'scheduled' && (
            <Input type="time" aria-label={`${a.label} time`} className="w-32" value={time}
              onChange={(e) => setTime(e.target.value)} onBlur={() => time !== a.schedule && update.mutate({ schedule: time })} />
          )}
        </div>
        {a.enabled && a.next_run_at && a.mode === 'scheduled' && <span className="text-sm text-muted-foreground">Next: {when(a.next_run_at)}</span>}
      </div>
      <div className="text-sm">
        {a.last_run ? (
          <>
            <span className={cn('rounded-sm px-1.5 py-0.5 text-xs font-medium', RESULT_TONE[a.last_run.result])}>{STATUS_LABEL[a.last_run.result]}</span>
            <span className="ml-2 text-muted-foreground">{formatShortDateTime(a.last_run.started_at)}</span>
            <span className="block">{lastRunSummary(a.last_run)}</span>
          </>
        ) : <span className="text-muted-foreground">Hasn't run yet.</span>}
        <ErrorText error={update.error || run.error} />
      </div>
      <Button variant="outline" size="sm" className="justify-self-start" disabled={run.isPending} onClick={() => run.mutate()}
        aria-label={`Run ${a.label} now`}>Run now</Button>
    </li>
  )
}

export default function Automations() {
  const autos = useQuery({ queryKey: ['automations'], queryFn: () => api.get<AutomationRow[]>('/api/automations'), refetchInterval: 10_000 })
  const runs = useQuery({ queryKey: ['automation-runs'], queryFn: () => api.get<AutomationRunRow[]>('/api/automations/runs?limit=200'), refetchInterval: 5_000 })
  const label = Object.fromEntries((autos.data ?? []).map((a) => [a.key, a.label]))
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Automations" lead="What runs by itself while the app is open, and when it last ran." />
      <p className="-mt-2 text-[15px] text-muted-foreground">
        Automations run only while JobFinder is open. A daily one that was missed while it was closed runs once when you start it.
      </p>
      <ErrorText error={autos.error} />
      <section className="flex flex-col gap-3">
        <ul className="divide-y rounded-lg border bg-card">
          {(autos.data ?? []).map((a) => <AutomationItem key={a.key} a={a} />)}
        </ul>
      </section>
      <RunLog runs={runs.data ?? []} labels={label} error={runs.error} />
    </div>
  )
}

const CHIP: Record<RowStatus, string> = {
  ok: 'bg-selected text-foreground', error: 'bg-danger-bg text-danger', paused: 'bg-attention-bg text-attention',
  skipped: 'bg-muted text-muted-foreground', running: 'bg-attention-bg text-attention',
}
const NUMBERS = [['fetched', 'Fetched'], ['new', 'New'], ['merged', 'Merged'], ['hidden', 'Hidden'], ['requests', 'Requests']] as const
const PAGE = 20

/** Newest first, one row per source of each fetch (or per run for the other automations), filterable, 20 at a time. */
function RunLog({ runs, labels, error }: { runs: AutomationRunRow[]; labels: Record<string, string>; error: unknown }) {
  // Newest first by start time (ids follow insertion order, which a catch-up run or an import can break).
  const rows = useMemo(() => [...runs].sort((a, b) => Date.parse(b.started_at) - Date.parse(a.started_at) || b.id - a.id)
    .flatMap((r) => runRows(r, labels[r.automation_key] ?? r.automation_key)), [runs, labels])
  const [filter, setFilter] = useState('')
  const [shown, setShown] = useState(PAGE)
  const [open, setOpen] = useState<Set<string>>(new Set())
  const groups = useMemo(() => {
    const seen = new Map<string, string>()
    for (const r of rows) if (!seen.has(r.group)) seen.set(r.group, r.name)
    return [...seen.entries()]
  }, [rows])
  const visible = rows.filter((r) => !filter || r.group === filter)
  const toggle = (k: string) => setOpen((o) => { const n = new Set(o); if (n.has(k)) n.delete(k); else n.add(k); return n })
  return (
    <section aria-labelledby="run-log" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="run-log" className="text-lg font-semibold">Run log</h2>
        <NativeSelect label="Show runs of" value={filter} onChange={(v) => { setFilter(v); setShown(PAGE) }}
          options={[{ value: '', label: 'All automations and sources' }, ...groups.map(([value, label]) => ({ value, label }))]} />
      </div>
      <ErrorText error={error} />
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full text-[15px]">
          <thead className="border-b text-left text-sm text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">When</th>
              <th scope="col" className="px-4 py-2 font-medium">Source</th>
              <th scope="col" className="px-4 py-2 font-medium">Status</th>
              {NUMBERS.map(([, l]) => <th key={l} scope="col" className="px-3 py-2 text-right font-medium">{l}</th>)}
              <th scope="col" className="px-4 py-2"><span className="sr-only">Details</span></th>
            </tr>
          </thead>
          <tbody>
            {visible.slice(0, shown).map((r) => <LogRow key={r.key} row={r} open={open.has(r.key)} onToggle={() => toggle(r.key)} />)}
            {visible.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">{rows.length ? 'No runs for this one yet.' : 'Nothing has run yet. Runs show up here as they happen.'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {visible.length > shown && (
        <Button variant="outline" className="self-center" onClick={() => setShown((n) => n + PAGE)}>
          Show more ({visible.length - shown} older)
        </Button>
      )}
    </section>
  )
}

function LogRow({ row, open, onToggle }: { row: RunLogRow; open: boolean; onToggle: () => void }) {
  const id = `run-details-${row.key}`
  return (
    <Fragment>
      <tr className={cn('border-t align-top first:border-t-0', open && 'bg-muted/40')}>
        <td className="px-4 py-2.5 whitespace-nowrap tabular-nums">{formatShortDateTime(row.at)}</td>
        <td className="px-4 py-2.5">
          <span className="font-medium">{row.name}</span>
          {row.meta && <span className="block text-sm text-muted-foreground">{row.meta}</span>}
        </td>
        <td className="px-4 py-2.5"><span className={cn('rounded-sm px-1.5 py-0.5 text-xs font-medium', CHIP[row.status])}>{STATUS_LABEL[row.status]}</span></td>
        {NUMBERS.map(([k]) => (
          <td key={k} className="px-3 py-2.5 text-right tabular-nums">{row.numbers ? row.numbers[k] : <span className="text-muted-foreground">–</span>}</td>
        ))}
        <td className="px-4 py-2 text-right">
          {row.details.length > 0 && (
            <Button size="sm" variant="ghost" aria-expanded={open} aria-controls={id} onClick={onToggle}>
              {open ? 'Hide details' : 'Details'}
            </Button>
          )}
        </td>
      </tr>
      {open && (
        <tr id={id} className="bg-muted/40">
          <td />
          <td colSpan={8} className="px-4 pb-3 text-sm">
            <ul className="flex max-w-[75ch] list-disc flex-col gap-1 pl-5">{row.details.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </td>
        </tr>
      )}
    </Fragment>
  )
}
