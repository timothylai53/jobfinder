import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { SearchProfileRow, SourceRow } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { ErrorText, Field, ListInput, NativeSelect } from './common'
import { sourceStatus } from './FetchNowDialog'
import { formatDateTime } from '@/lib/score'

const JOB_TYPES = [
  { value: 'fulltime', label: 'Full time' }, { value: 'parttime', label: 'Part time' },
  { value: 'contract', label: 'Contract' }, { value: 'internship', label: 'Internship' }, { value: '', label: 'Any' },
]
const SOURCE_KEYS = ['jobstreet', 'linkedin', 'indeed', 'glassdoor']

// ---------- search profiles ----------

function ProfileEditor({ p, onDone }: { p: SearchProfileRow | null; onDone: () => void }) {
  const qc = useQueryClient()
  const [v, setV] = useState<Omit<SearchProfileRow, 'id'>>(
    p ?? { name: '', keywords: [], locations: [], job_type: 'fulltime', days: 7, sources: [], max_results: 0, enabled: true })
  const set = <K extends keyof typeof v>(k: K, val: (typeof v)[K]) => setV({ ...v, [k]: val })
  const save = useMutation({
    mutationFn: () => (p ? api.put(`/api/search-profiles/${p.id}`, v) : api.post('/api/search-profiles', v)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['search-profiles'] }); onDone() },
  })
  return (
    <div className="grid gap-3 rounded-lg border bg-muted/30 p-4 sm:grid-cols-2">
      <Field label="Name"><Input value={v.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. KL/Selangor" /></Field>
      <Field label="Job type"><NativeSelect className="h-9" value={v.job_type} onChange={(x) => set('job_type', x)} options={JOB_TYPES} /></Field>
      <Field label="Keywords (comma-separated; each is its own search)" className="sm:col-span-2">
        <ListInput value={v.keywords} onChange={(x) => set('keywords', x)} placeholder="e.g. software engineer, junior software engineer" />
      </Field>
      <Field label="Locations (comma-separated; “Remote” allowed)" className="sm:col-span-2">
        <ListInput value={v.locations} onChange={(x) => set('locations', x)} placeholder="e.g. Kuala Lumpur, Selangor, Remote" />
      </Field>
      <Field label="Posted within the last (days)"><Input type="number" min={1} max={31} value={v.days} onChange={(e) => set('days', Number(e.target.value))} /></Field>
      <Field label="Max jobs per source (0 = the source's limit)"><Input type="number" min={0} value={v.max_results} onChange={(e) => set('max_results', Number(e.target.value))} /></Field>
      <div className="sm:col-span-2">
        <span className="text-sm font-medium text-muted-foreground">Sources (none ticked = every enabled source)</span>
        <div className="mt-1 flex flex-wrap gap-4">
          {SOURCE_KEYS.map((k) => (
            <label key={k} className="flex items-center gap-1.5 text-[15px] capitalize">
              <input type="checkbox" checked={v.sources.includes(k)} onChange={(e) => set('sources', e.target.checked ? [...v.sources, k] : v.sources.filter((s) => s !== k))} />
              {k === 'jobstreet' ? 'JobStreet' : k === 'linkedin' ? 'LinkedIn' : k}
            </label>
          ))}
        </div>
      </div>
      <div className="flex items-center justify-end gap-2 sm:col-span-2">
        <ErrorText error={save.error} />
        <Button variant="ghost" onClick={onDone}>Cancel</Button>
        <Button disabled={!v.name.trim() || v.keywords.length === 0 || save.isPending} onClick={() => save.mutate()}>Save search profile</Button>
      </div>
    </div>
  )
}

export function SearchProfiles() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['search-profiles'], queryFn: () => api.get<SearchProfileRow[]>('/api/search-profiles') })
  const [editing, setEditing] = useState<number | 'new' | null>(null)
  const toggle = useMutation({
    mutationFn: (p: SearchProfileRow) => api.put(`/api/search-profiles/${p.id}`, { ...p, enabled: !p.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['search-profiles'] }),
  })
  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/search-profiles/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['search-profiles'] }),
  })
  return (
    <div className="flex flex-col gap-3">
      <ErrorText error={q.error || toggle.error || del.error} />
      {(q.data ?? []).map((p) => editing === p.id ? <ProfileEditor key={p.id} p={p} onDone={() => setEditing(null)} /> : (
        <div key={p.id} className={cn('flex flex-wrap items-start gap-3 rounded-lg border bg-card p-4', !p.enabled && 'opacity-60')}>
          <input type="checkbox" className="mt-1.5" aria-label={`Use ${p.name}`} checked={p.enabled} onChange={() => toggle.mutate(p)} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{p.name}</div>
            <div className="text-[15px]">{p.keywords.join(', ')}</div>
            <div className="text-sm text-muted-foreground">
              {p.locations.join(', ') || 'anywhere'} · {JOB_TYPES.find((t) => t.value === p.job_type)?.label} · last {p.days} days
              {p.sources.length > 0 && ` · only ${p.sources.join(', ')}`}
            </div>
          </div>
          <Button size="sm" variant="outline" onClick={() => setEditing(p.id)}>Edit</Button>
          <Button size="sm" variant="ghost" onClick={() => confirm(`Delete search profile “${p.name}”?`) && del.mutate(p.id)}>Delete</Button>
        </div>
      ))}
      {editing === 'new' ? <ProfileEditor p={null} onDone={() => setEditing(null)} /> : (
        <Button variant="outline" className="self-start" onClick={() => setEditing('new')}>Add a search profile</Button>
      )}
      <p className="text-sm text-muted-foreground">Each keyword × location is one search per source, so fewer, broader keywords mean fewer requests.</p>
    </div>
  )
}

// ---------- sources ----------

function SourceCard({ s }: { s: SourceRow }) {
  const qc = useQueryClient()
  const [results, setResults] = useState(s.max_results)
  const [runs, setRuns] = useState(s.max_runs_per_day)
  useEffect(() => { setResults(s.max_results); setRuns(s.max_runs_per_day) }, [s.max_results, s.max_runs_per_day])
  const done = () => { qc.invalidateQueries({ queryKey: ['sources'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }) }
  const save = useMutation({
    mutationFn: (body: Partial<SourceRow>) => api.put(`/api/sources/${s.key}`, { enabled: s.enabled, max_results: results, max_runs_per_day: runs, ...body }),
    onSuccess: done,
  })
  const resume = useMutation({ mutationFn: () => api.post(`/api/sources/${s.key}/resume`), onSuccess: done })
  const st = sourceStatus(s)
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div>
        <label className="flex flex-wrap items-center gap-x-2 font-semibold">
          <input type="checkbox" checked={s.enabled} onChange={(e) => save.mutate({ enabled: e.target.checked })} />
          {s.label}
          <span className={cn('text-sm font-normal', st.tone)}>{st.text}</span>
        </label>
        <p className="text-sm text-muted-foreground">
          {s.last_run_at ? `Last run ${formatDateTime(s.last_run_at)}: ` : 'Not run yet. '}
          {s.status !== 'ok' ? s.last_error : s.last_result}
        </p>
        {s.key === 'glassdoor' && <p className="text-sm text-muted-foreground">Glassdoor has little Malaysia coverage; off by default.</p>}
        <ErrorText error={save.error || resume.error} />
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={`Jobs per run (max ${s.hard_max_results})`}>
          <Input type="number" min={1} max={s.hard_max_results} className="w-24" value={results} onChange={(e) => setResults(Number(e.target.value))}
            onBlur={() => results !== s.max_results && save.mutate({})} />
        </Field>
        <Field label={`Runs per day (max ${s.hard_max_runs_per_day})`}>
          <Input type="number" min={1} max={s.hard_max_runs_per_day} className="w-24" value={runs} onChange={(e) => setRuns(Number(e.target.value))}
            onBlur={() => runs !== s.max_runs_per_day && save.mutate({})} />
        </Field>
        {s.status === 'paused' && <Button size="sm" variant="outline" onClick={() => resume.mutate()}>Resume now</Button>}
      </div>
    </div>
  )
}

export function JobSources() {
  const q = useQuery({ queryKey: ['sources'], queryFn: () => api.get<SourceRow[]>('/api/sources'), refetchInterval: 15_000 })
  return (
    <div className="flex flex-col gap-3">
      <ErrorText error={q.error} />
      {(q.data ?? []).map((s) => <SourceCard key={s.key} s={s} />)}
      <p className="text-sm text-muted-foreground">
        No logins, ever: sources only read public, logged-out pages. Requests go one at a time with 2–6 s pauses. A source that answers
        “too many requests” or “forbidden”, or fails 3 times in a row, is paused for 24 hours and you get a notification.
      </p>
    </div>
  )
}
