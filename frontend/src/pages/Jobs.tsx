import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { JobSummary } from '@/api/types'
import { ErrorText, NativeSelect, PageHeader, ScoreBadge } from '@/components/common'
import FetchNowDialog from '@/components/FetchNowDialog'
import ImportJobDialog from '@/components/ImportJobDialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate, formatSalary, sortJobs, type SortKey } from '@/lib/score'
import { cn } from '@/lib/utils'
import { usePendingDeletes } from '@/lib/pendingDeletes'

const SORTS: { value: SortKey; label: string }[] = [
  { value: 'score', label: 'Score' },
  { value: 'fetched_at', label: 'Added' },
  { value: 'posted_date', label: 'Posted' },
  { value: 'title', label: 'Title' },
  { value: 'company', label: 'Company' },
]

export default function Jobs() {
  const qc = useQueryClient()
  const [params] = useSearchParams()
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => api.get<JobSummary[]>('/api/jobs') })
  const [tab, setTab] = useState<'visible' | 'hidden'>('visible')
  const [q, setQ] = useState('')
  const [minScore, setMinScore] = useState('')
  const [onlyUntracked, setOnlyUntracked] = useState(false)
  const [sort, setSort] = useState<SortKey>('score')
  const [desc, setDesc] = useState(true)

  const save = useMutation({
    mutationFn: (jobId: number) => api.post('/api/applications', { job_id: jobId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
  const unhide = useMutation({
    mutationFn: (jobId: number) => api.patch(`/api/jobs/${jobId}`, { hidden: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const deleting = usePendingDeletes()
  const all = (jobs.data ?? []).filter((j) => !deleting.has(j.id))
  const hiddenCount = all.filter((j) => j.hidden).length
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const min = minScore === '' ? null : Number(minScore)
    const filtered = all.filter(
      (j) =>
        j.hidden === (tab === 'hidden') &&
        (!needle || `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(needle)) &&
        (min === null || (j.score ?? 0) >= min) &&
        (!onlyUntracked || !j.application_id),
    )
    return sortJobs(filtered, sort, desc)
  }, [all, tab, q, minScore, onlyUntracked, sort, desc])

  return (
    <div>
      <PageHeader title="Jobs" lead="Every job you have fetched or imported, scored against your Experience Bank.">
        <FetchNowDialog />
        <ImportJobDialog defaultOpen={params.get("import") === "1"} />
      </PageHeader>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border bg-background p-0.5 text-sm">
          {(['visible', 'hidden'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn('rounded-md px-3 py-1', tab === t && 'bg-muted font-medium')}
            >
              {t === 'visible' ? `Jobs (${all.length - hiddenCount})` : `Hidden (${hiddenCount})`}
            </button>
          ))}
        </div>
        <Input className="w-56" placeholder="Search title, company, location" value={q} onChange={(e) => setQ(e.target.value)} />
        <Input className="w-28" type="number" placeholder="Min score" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
        <label className="flex items-center gap-1 text-sm">
          <input type="checkbox" checked={onlyUntracked} onChange={(e) => setOnlyUntracked(e.target.checked)} />
          Not in tracker
        </label>
        <span className="ml-auto text-sm text-muted-foreground">Sort</span>
        <NativeSelect value={sort} onChange={(v) => setSort(v as SortKey)} options={SORTS} />
        <Button variant="outline" size="sm" onClick={() => setDesc(!desc)}>
          {desc ? '↓' : '↑'}
        </Button>
      </div>

      <ErrorText error={jobs.error || save.error} />
      <div className="rounded-lg border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Score</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Location</TableHead>
              <TableHead>Salary</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Posted / added</TableHead>
              <TableHead className="w-32"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((j) => (
              <TableRow key={j.id}>
                <TableCell>
                  <ScoreBadge score={j.score} gated={j.gate_flags.length > 0} rough={j.summary_only || !!j.low_confidence} />
                  {(j.summary_only || j.low_confidence) && (
                    <div className="mt-0.5 text-[11px] leading-tight whitespace-nowrap text-muted-foreground" title={j.low_confidence || undefined}>
                      {j.summary_only ? 'rough (summary only)' : 'low confidence'}
                    </div>
                  )}
                </TableCell>
                <TableCell className="max-w-72 whitespace-normal">
                  <Link to={`/jobs/${j.id}`} className="font-medium hover:underline">
                    {j.title}
                  </Link>
                  {j.hidden && <div className="text-xs text-muted-foreground">{j.hidden_reason}</div>}
                </TableCell>
                <TableCell>{j.company}</TableCell>
                <TableCell>{j.location}</TableCell>
                <TableCell>{formatSalary(j.salary_min, j.salary_max, j.salary_currency)}</TableCell>
                <TableCell>{j.sources.join(', ')}</TableCell>
                <TableCell>{formatDate(j.posted_date ?? j.fetched_at)}</TableCell>
                <TableCell className="text-right">
                  {j.hidden ? (
                    <Button size="sm" variant="outline" onClick={() => unhide.mutate(j.id)}>
                      Unhide
                    </Button>
                  ) : j.application_status ? (
                    <Link to="/tracker" className="text-sm text-muted-foreground hover:underline">
                      {j.application_status}
                    </Link>
                  ) : (
                    <Button size="sm" variant="outline" disabled={save.isPending} onClick={() => save.mutate(j.id)}>
                      Save
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="py-8 text-center text-muted-foreground">
                  {jobs.isLoading ? 'Loading…' : all.length === 0 ? 'No jobs yet. Use “Import job” to paste a JD.' : 'No jobs match these filters.'}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
