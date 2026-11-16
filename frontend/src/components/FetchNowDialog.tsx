import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { AutomationRunRow, SearchProfileRow, SourceRow } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { anyRunning, CAP_STORAGE_KEY, confirmAgainText, DEFAULT_CAP, fetchButtonLabel, fetchedToday } from '@/lib/fetchPlan'
import { cn } from '@/lib/utils'
import { ErrorText, NativeSelect } from './common'
import { formatDateTime } from '@/lib/score'

export function sourceStatus(s: SourceRow): { text: string; tone: string } {
  if (s.running) return { text: 'Fetching now…', tone: 'text-attention' }
  if (!s.enabled) return { text: 'Off', tone: 'text-muted-foreground' }
  if (s.status === 'paused') return { text: `Paused until ${formatDateTime(s.paused_until)}`, tone: 'text-red-700' }
  if (s.status === 'error') return { text: 'Last run failed', tone: 'text-attention' }
  if (s.runs_today >= s.max_runs_per_day) return { text: 'Daily limit reached', tone: 'text-muted-foreground' }
  return { text: 'Ready', tone: 'text-primary' }
}

/** "Fetch now": pick sources (and an optional small cap), then watch the run's per-source results. */
export default function FetchNowDialog() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<string[] | null>(null)
  // Defaults to 5 and remembers the last value (also across reopening the dialog and reloading the page)
  const [cap, setCapState] = useState(() => {
    try { return localStorage.getItem(CAP_STORAGE_KEY) ?? DEFAULT_CAP } catch { return DEFAULT_CAP }
  })
  const setCap = (v: string) => {
    setCapState(v)
    try { localStorage.setItem(CAP_STORAGE_KEY, v) } catch { /* storage blocked: still works for this visit */ }
  }
  const [profileId, setProfileId] = useState('')
  const [runId, setRunId] = useState<number | null>(null)
  const sources = useQuery({
    queryKey: ['sources'],
    queryFn: () => api.get<SourceRow[]>('/api/sources'),
    enabled: open,
    refetchInterval: (q) => (q.state.data?.some((s) => s.running) ? 2000 : false),
  })
  const profiles = useQuery({ queryKey: ['search-profiles'], queryFn: () => api.get<SearchProfileRow[]>('/api/search-profiles'), enabled: open })
  const run = useQuery({
    queryKey: ['automation-run', runId],
    queryFn: () => api.get<AutomationRunRow>(`/api/automations/runs/${runId}`),
    enabled: runId !== null,
    refetchInterval: (q) => (q.state.data && q.state.data.result !== 'running' ? false : 1500),
  })
  const start = useMutation({
    mutationFn: () => api.post<{ run_id: number }>('/api/fetch', {
      source_keys: chosen, results_cap: cap ? Number(cap) : null, profile_ids: profileId ? [Number(profileId)] : null,
    }),
    onSuccess: (r) => setRunId(r.run_id),
  })

  const rows = sources.data ?? []
  const runnable = rows.filter((s) => s.enabled && s.can_run && !s.running)
  const chosen = picked ?? runnable.map((s) => s.key)
  const chosenRows = rows.filter((s) => chosen.includes(s.key))
  const busy = anyRunning(chosenRows)
  // Every way of closing resets the dialog to the form (the limit is kept), so reopening never shows an old run
  const close = () => { setOpen(false); setRunId(null); setPicked(null); setProfileId('') }
  const go = () => {
    const again = fetchedToday(chosenRows)
    if (again.length > 0 && !confirm(confirmAgainText(again))) return
    start.mutate()
  }
  const activeProfiles = (profiles.data ?? []).filter((p) => p.enabled)
  const done = run.data && run.data.result !== 'running'
  useEffect(() => {
    if (!done) return
    for (const k of ['jobs', 'dashboard', 'notifications', 'sources', 'automations']) qc.invalidateQueries({ queryKey: [k] })
  }, [done, qc])

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : close())}>
      <DialogTrigger asChild>
        <Button variant="outline">Fetch now</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl">Fetch jobs now</DialogTitle>
          <DialogDescription className="text-[15px]">
            Logged out, one request at a time with 2–6 s pauses. A source that answers “too many requests” is paused for 24 hours.
          </DialogDescription>
        </DialogHeader>

        {runId === null ? (
          <div className="flex flex-col gap-4">
            {rows[0]?.fake_mode && (
              <p className="rounded-md border border-attention-edge bg-attention-bg px-3 py-2 text-sm text-attention">
                Fake sources are on (JOBFINDER_FAKE_SOURCES=1): saved test data is replayed, no site is contacted.
              </p>
            )}
            <div>
              <h3 className="mb-1 font-medium">Sources</h3>
              <ul className="flex flex-col divide-y rounded-lg border">
                {rows.map((s) => {
                  const st = sourceStatus(s)
                  const usable = s.enabled && s.can_run && !s.running
                  return (
                    <li key={s.key} className="flex items-center gap-3 px-3 py-2 text-[15px]">
                      <input
                        type="checkbox"
                        aria-label={`Fetch from ${s.label}`}
                        disabled={!usable}
                        checked={usable && chosen.includes(s.key)}
                        onChange={(e) => setPicked(e.target.checked ? [...chosen, s.key] : chosen.filter((k) => k !== s.key))}
                      />
                      <span className="w-24 font-medium">{s.label}</span>
                      <span className={cn('flex-1 text-sm', st.tone)}>{st.text}</span>
                      <span className="text-sm text-muted-foreground">up to {s.max_results} jobs, {s.runs_today}/{s.max_runs_per_day} runs today</span>
                    </li>
                  )
                })}
              </ul>
            </div>
            <label className="flex flex-wrap items-center gap-2 text-sm">
              Search profile
              <NativeSelect
                value={profileId}
                onChange={setProfileId}
                options={[{ value: '', label: `All enabled (${activeProfiles.map((p) => p.name).join(', ') || 'none'})` },
                  ...activeProfiles.map((p) => ({
                    value: String(p.id),
                    label: `${p.name}: ${p.keywords.length} keyword(s) × ${p.locations.length || 1} location(s)`,
                  }))]}
              />
              <Link to="/settings?section=search-profiles" className="underline">Edit profiles</Link>
            </label>
            <label className="flex items-center gap-2 text-sm">
              Limit each source to
              <Input type="number" min={1} max={100} className="w-20" value={cap} placeholder="—" onChange={(e) => setCap(e.target.value)} />
              jobs this time {cap.trim() === '' ? <span className="font-medium text-attention">(empty: each source's own limit applies)</span> : '(5 for a careful test run)'}
            </label>
            <div className="flex items-center justify-end gap-2">
              <ErrorText error={start.error} />
              <Button disabled={chosen.length === 0 || activeProfiles.length === 0 || start.isPending || busy} onClick={go}>
                {busy ? 'A fetch for this source is running…' : fetchButtonLabel(chosenRows, cap)}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-[15px] font-medium">
              {!done ? 'Fetching… this can take a few minutes because of the pauses between requests.' :
                run.data?.result === 'error' ? 'Finished with problems.' : `Finished: ${run.data?.items_processed} new job(s).`}
            </p>
            <ul className="flex flex-col gap-1 rounded-lg border bg-muted/40 p-3 text-sm">
              {(run.data?.message || '').split('\n').filter(Boolean).map((line, i) => <li key={i}>{line}</li>)}
              {run.data?.error && <li className="text-red-700">{run.data.error}</li>}
              {!done && <li className="text-muted-foreground">Waiting for results…</li>}
            </ul>
            {done && (
              <div className="flex justify-end gap-2">
                <Button variant="outline" asChild><Link to="/automations" onClick={close}>Open run log</Link></Button>
                <Button onClick={close}>Done</Button>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
