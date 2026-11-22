import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { AutomationRow, AutomationRunRow } from '@/api/types'
import { ErrorText, NativeSelect, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { formatDateTime, formatShortDateTime } from '@/lib/score'
import { runRows, STATUS_LABEL, type RowStatus, type RunLogRow } from '@/lib/runlog'
import { useLocalCopy } from '@/lib/hooks'

const RESULT_TONE: Record<string, string> = {
  ok: 'bg-selected text-foreground', error: 'bg-danger-bg text-danger',
  skipped: 'bg-muted text-muted-foreground', running: 'bg-attention-bg text-attention',
}

function when(iso: string | null | undefined) {
  return iso ? formatDateTime(iso) : '—'
}

function scheduleText(a: AutomationRow) {
  if (a.mode === 'manual') return 'Only when I click Run now'
  return a.daily ? `Every day at ${a.schedule}` : 'Right after Fetch jobs'
}

function AutomationCard({ a }: { a: AutomationRow }) {
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
  return (
    <div className="grid gap-x-4 gap-y-2 rounded-lg border bg-card p-4 md:grid-cols-[minmax(0,1fr)_auto]">
      <div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 font-semibold">
            <input type="checkbox" checked={a.enabled} onChange={(e) => update.mutate({ enabled: e.target.checked })} />
            {a.label}
          </label>
          {a.key === 'fetch_jobs' && !a.enabled && (
            <span className="rounded bg-muted px-1.5 text-xs text-muted-foreground">off until you turn it on</span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{a.description}</p>
        <p className="mt-1 text-sm">
          {a.enabled ? scheduleText(a) : 'Off'}
          {a.enabled && a.next_run_at && a.mode === 'scheduled' && <span className="text-muted-foreground"> · next {when(a.next_run_at)}</span>}
        </p>
        {a.last_run && (
          <p className="mt-1 text-sm">
            <span className={cn('rounded-sm px-1.5 py-0.5 text-xs font-medium', RESULT_TONE[a.last_run.result])}>{STATUS_LABEL[a.last_run.result]}</span>{' '}
            <span className="text-muted-foreground">last run {when(a.last_run.started_at)}: {a.last_run.error || a.last_run.message.split('\n')[0]}</span>
          </p>
        )}
        <ErrorText error={update.error || run.error} />
      </div>
      <div className="flex flex-wrap items-center gap-2 md:justify-end">
        <NativeSelect
          value={a.mode}
          onChange={(v) => update.mutate({ mode: v as AutomationRow['mode'] })}
          options={[{ value: 'scheduled', label: 'Scheduled' }, { value: 'manual', label: 'Manual only' }]}
        />
        {a.daily && (
          <Input
            type="time"
            aria-label={`${a.label} time`}
            className="w-36"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            onBlur={() => time !== a.schedule && update.mutate({ schedule: time })}
          />
        )}
        <Button variant="outline" size="sm" disabled={run.isPending} onClick={() => run.mutate()}>Run now</Button>
      </div>
    </div>
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
        {(autos.data ?? []).map((a) => <AutomationCard key={a.key} a={a} />)}
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
