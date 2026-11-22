import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { AutomationRow, AutomationRunRow } from '@/api/types'
import { ErrorText, NativeSelect, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { formatDateTime } from '@/lib/score'

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
  const [time, setTime] = useState(a.schedule)
  useEffect(() => setTime(a.schedule), [a.schedule])
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
            <span className={cn('rounded px-1.5 text-xs', RESULT_TONE[a.last_run.result])}>{a.last_run.result}</span>{' '}
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
  const runs = useQuery({ queryKey: ['automation-runs'], queryFn: () => api.get<AutomationRunRow[]>('/api/automations/runs?limit=50'), refetchInterval: 5_000 })
  const [open, setOpen] = useState<number | null>(null)
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
      <section>
        <h2 className="mb-2 text-lg font-semibold">Run log</h2>
        <div className="overflow-hidden rounded-lg border bg-card">
          <table className="w-full text-[15px]">
            <thead className="bg-muted/60 text-left text-sm text-muted-foreground">
              <tr><th className="px-3 py-2">When</th><th className="px-3 py-2">Automation</th><th className="px-3 py-2">How</th><th className="px-3 py-2">Result</th><th className="px-3 py-2">Items</th><th className="px-3 py-2">Details</th></tr>
            </thead>
            <tbody className="divide-y">
              {(runs.data ?? []).map((r) => (
                <tr key={r.id} className="align-top">
                  <td className="px-3 py-2 whitespace-nowrap">{when(r.started_at)}</td>
                  <td className="px-3 py-2">{label[r.automation_key] ?? r.automation_key}</td>
                  <td className="px-3 py-2 text-muted-foreground">{r.trigger}</td>
                  <td className="px-3 py-2"><span className={cn('rounded px-1.5 text-xs', RESULT_TONE[r.result])}>{r.result}</span></td>
                  <td className="px-3 py-2 tabular-nums">{r.items_processed}</td>
                  <td className="px-3 py-2 text-sm">
                    {r.error ? <span className="text-danger">{r.error}</span> : (
                      <button className="text-left hover:underline" onClick={() => setOpen(open === r.id ? null : r.id)}>
                        {open === r.id ? <pre className="font-sans whitespace-pre-wrap">{r.message}</pre> : r.message.split('\n')[0]}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {(runs.data ?? []).length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">No runs yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
