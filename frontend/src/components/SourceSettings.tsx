import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import type { SearchProfileRow, SourceRow } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useToast } from '@/lib/toast'
import { ErrorText, Field, ListInput, NativeSelect } from './common'
import { sourceStatus } from '@/lib/sources'
import { formatDateTime } from '@/lib/score'
import { useLocalCopy } from '@/lib/hooks'

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

/** One row of the Job sources table: on/off, health, and the two limits (saved when a box loses focus). */
function SourceRowView({ s }: { s: SourceRow }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [results, setResults] = useLocalCopy(s.max_results)
  const [runs, setRuns] = useLocalCopy(s.max_runs_per_day)
  const done = () => { qc.invalidateQueries({ queryKey: ['sources'] }); qc.invalidateQueries({ queryKey: ['dashboard'] }) }
  const save = useMutation({
    mutationFn: (body: Partial<SourceRow>) => api.put(`/api/sources/${s.key}`, { enabled: s.enabled, max_results: results, max_runs_per_day: runs, ...body }),
    onSuccess: (_d, body) => { done(); if (!('enabled' in body)) toast({ message: `${s.label} limits saved.` }) },
  })
  const resume = useMutation({ mutationFn: () => api.post(`/api/sources/${s.key}/resume`), onSuccess: done })
  const st = sourceStatus(s)
  const last = s.last_run_at ? `Last run ${formatDateTime(s.last_run_at)}` : 'Not run yet'
  const detail = s.status !== 'ok' ? s.last_error : s.last_result
  return (
    <tr className="border-t align-top first:border-t-0">
      <td className="px-4 py-3">
        <input type="checkbox" className="mt-1 size-4 accent-foreground" aria-label={`Use ${s.label}`} checked={s.enabled}
          onChange={(e) => save.mutate({ enabled: e.target.checked })} />
      </td>
      <td className="px-4 py-3">
        <span className={cn('font-medium', !s.enabled && 'text-muted-foreground')}>{s.label}</span>
        <span className={cn('ml-2 text-sm', st.tone)}>{st.text}</span>
        <span className="block text-sm text-muted-foreground" title={detail || undefined}>{last}{detail ? `: ${detail}` : '.'}</span>
        {s.key === 'glassdoor' && <span className="block text-sm text-muted-foreground">Little Malaysia coverage, so it starts off.</span>}
        {s.status === 'paused' && <Button size="sm" variant="outline" className="mt-2" onClick={() => resume.mutate()}>Resume now</Button>}
        <ErrorText error={save.error || resume.error} />
      </td>
      <td className="px-4 py-3">
        <Input type="number" min={1} max={s.hard_max_results} className="w-20" aria-label={`${s.label}: jobs per run`} value={results}
          onChange={(e) => setResults(Number(e.target.value))} onBlur={() => results !== s.max_results && save.mutate({})} />
        <span className="mt-1 block text-xs text-muted-foreground">up to {s.hard_max_results}</span>
      </td>
      <td className="px-4 py-3">
        <Input type="number" min={1} max={s.hard_max_runs_per_day} className="w-20" aria-label={`${s.label}: runs per day`} value={runs}
          onChange={(e) => setRuns(Number(e.target.value))} onBlur={() => runs !== s.max_runs_per_day && save.mutate({})} />
        <span className="mt-1 block text-xs text-muted-foreground">up to {s.hard_max_runs_per_day}</span>
      </td>
    </tr>
  )
}

export function JobSources() {
  const q = useQuery({ queryKey: ['sources'], queryFn: () => api.get<SourceRow[]>('/api/sources'), refetchInterval: 15_000 })
  return (
    <div className="flex flex-col gap-3">
      <ErrorText error={q.error} />
      <div className="overflow-x-auto rounded-lg border bg-background">
        <table className="w-full text-[15px]">
          <thead className="border-b text-left text-sm text-muted-foreground">
            <tr>
              <th scope="col" className="w-12 px-4 py-2 font-medium"><span className="sr-only">On</span></th>
              <th scope="col" className="px-4 py-2 font-medium">Source</th>
              <th scope="col" className="w-32 px-4 py-2 font-medium">Jobs per run</th>
              <th scope="col" className="w-32 px-4 py-2 font-medium">Runs per day</th>
            </tr>
          </thead>
          <tbody>{(q.data ?? []).map((s) => <SourceRowView key={s.key} s={s} />)}</tbody>
        </table>
      </div>
      <p className="text-sm text-muted-foreground">
        No logins, ever: sources only read public, logged-out pages. Requests go one at a time with 2–6 s pauses. A source that answers
        “too many requests” or “forbidden”, or fails 3 times in a row, is paused for 24 hours and you get a notification.
      </p>
    </div>
  )
}
