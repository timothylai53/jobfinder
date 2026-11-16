import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import { STATUSES, type Application, type DeepAnalysisResult, type JobDetail as JobDetailT, type Status } from '@/api/types'
import Breakdown from '@/components/Breakdown'
import AiTools from '@/components/ai/AiTools'
import DocumentsCard, { useDocuments } from '@/components/ai/DocumentsCard'
import { DeepAnalysisView } from '@/components/ai/AnalysisViews'
import PasteFullJdDialog from '@/components/PasteFullJdDialog'
import ProfileGaps from '@/components/ProfileGaps'
import { ErrorText, Field, NativeSelect, Notice, ScoreBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatSalary } from '@/lib/score'

export default function JobDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const imported = (location.state as { imported?: { duplicate: boolean; hidden: boolean; hidden_reason: string } } | null)?.imported
  const q = useQuery({ queryKey: ['job', id], queryFn: () => api.get<JobDetailT>(`/api/jobs/${id}`) })
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['job', id] })
    qc.invalidateQueries({ queryKey: ['jobs'] })
    qc.invalidateQueries({ queryKey: ['applications'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const save = useMutation({ mutationFn: () => api.post('/api/applications', { job_id: Number(id) }), onSuccess: invalidate })
  const patchApp = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch(`/api/applications/${q.data!.application!.id}`, body),
    onSuccess: invalidate,
  })
  const hide = useMutation({ mutationFn: (hidden: boolean) => api.patch(`/api/jobs/${id}`, { hidden }), onSuccess: invalidate })
  const del = useMutation({
    mutationFn: () => api.del(`/api/jobs/${id}`),
    onSuccess: () => {
      invalidate()
      navigate('/jobs')
    },
  })

  const [notes, setNotes] = useState('')
  useEffect(() => setNotes(q.data?.application?.notes ?? ''), [q.data?.application?.notes])

  if (q.isLoading) return <p>Loading…</p>
  if (q.error || !q.data) return <ErrorText error={q.error ?? 'Not found'} />
  const { job, match, application, history, summary_only: summaryOnly, low_confidence: lowConfidence } = q.data
  const roughLabel = summaryOnly ? 'rough (summary only)' : lowConfidence ? 'low confidence' : ''
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/jobs" className="text-sm text-muted-foreground hover:underline">
          ← Jobs
        </Link>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold">
              <ScoreBadge score={match?.total ?? null} gated={(match?.gate_flags.length ?? 0) > 0} rough={!!roughLabel} />
              {job.title}
              {roughLabel && <span className="text-sm font-normal text-muted-foreground">{roughLabel}</span>}
            </h1>
            <p className="text-sm text-muted-foreground">
              {[job.company, job.work_arrangement ? `${job.location} (${job.work_arrangement})` : job.location, salary, job.job_type].filter(Boolean).join(' · ')}
            </p>
            <p className="text-xs text-muted-foreground">
              Added {formatDate(job.fetched_at)} · source {job.sources.join(', ')}
              {job.urls.map((u) => (
                <a key={u} href={u} target="_blank" rel="noreferrer" className="ml-2 underline">
                  open posting
                </a>
              ))}
            </p>
          </div>
          <div className="flex gap-2">
            {!application && (
              <Button onClick={() => save.mutate()} disabled={save.isPending}>
                Save to tracker
              </Button>
            )}
            <Button variant="outline" onClick={() => hide.mutate(!job.hidden)}>
              {job.hidden ? 'Unhide' : 'Hide'}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm('Delete this job, its score and its tracker entry?')) del.mutate()
              }}
            >
              Delete
            </Button>
          </div>
        </div>
      </div>

      <ProfileGaps context="score" />
      {imported?.duplicate && <Notice tone="warn">This JD matched a job already saved, so it was merged into that job.</Notice>}
      {job.hidden && <Notice tone="warn">Hidden: {job.hidden_reason}</Notice>}
      {summaryOnly && (
        <Notice tone="warn">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>
              Only the search summary of this job was saved, so its score is <strong>rough</strong> and it won't trigger a
              high-match alert. Open the posting, copy the page and paste it to get the real score.
            </span>
            <PasteFullJdDialog jobId={job.id} title={job.title} url={job.urls[0]} size="sm" />
          </div>
        </Notice>
      )}
      {!summaryOnly && lowConfidence && (
        <Notice tone="warn">
          {lowConfidence}. The score is capped at 50, marked low confidence, and won't trigger a high-match alert.
          Check the JD below yourself.
        </Notice>
      )}
      <ErrorText error={save.error || patchApp.error || hide.error || del.error} />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Quick score{roughLabel && <span className="ml-2 text-sm font-normal text-muted-foreground">{roughLabel}</span>}</CardTitle>
          </CardHeader>
          <CardContent>{match ? <Breakdown data={match.breakdown} /> : <p>Not scored yet.</p>}</CardContent>
        </Card>
        <LatestAnalysis jobId={job.id} />
        </div>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Application</CardTitle>
            </CardHeader>
            <CardContent>
              {!application ? (
                <p className="text-sm text-muted-foreground">Not in the tracker yet. Use “Save to tracker”.</p>
              ) : (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-3 gap-3">
                    <Field label="Status">
                      <NativeSelect
                        value={application.status}
                        onChange={(v) => patchApp.mutate({ status: v as Status })}
                        options={[...STATUSES]}
                      />
                    </Field>
                    <Field label="Applied on">
                      <Input
                        type="date"
                        value={application.applied_at ?? ''}
                        onChange={(e) => patchApp.mutate({ applied_at: e.target.value || null })}
                      />
                    </Field>
                    <Field label="Follow up on">
                      <Input
                        type="date"
                        value={application.follow_up_at ?? ''}
                        onChange={(e) => patchApp.mutate({ follow_up_at: e.target.value || null })}
                      />
                    </Field>
                  </div>
                  <Field label="Notes">
                    <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== application.notes && patchApp.mutate({ notes })} />
                  </Field>
                  <div className="text-xs text-muted-foreground">
                    <div className="mb-1 font-medium">Status history</div>
                    {history.map((h) => (
                      <div key={h.id}>
                        {new Date(h.changed_at).toLocaleString('en-MY')}: {h.from_status ?? 'new'} → {h.to_status}
                      </div>
                    ))}
                  </div>
                  <VersionsSent application={application} onChange={(body) => patchApp.mutate(body)} />
                </div>
              )}
            </CardContent>
          </Card>

          <AiTools job={{ id: job.id, title: job.title, summaryOnly, lowConfidence }} />
          <DocumentsCard jobId={job.id} application={application} />

          <Card>
            <CardHeader>
              <CardTitle>Job description snapshot</CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap font-sans text-sm">{job.description}</pre>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

/** The newest deep analysis, shown under the quick score (brief §7: Job Detail shows the deep analysis, if any). */
function LatestAnalysis({ jobId }: { jobId: number }) {
  const docs = useDocuments(jobId)
  const latest = (docs.data ?? []).find((d) => d.type === 'deep_analysis')
  if (!latest) return null
  const data = latest.content as unknown as DeepAnalysisResult
  return (
    <Card>
      <CardHeader><CardTitle>Deep analysis <span className="text-sm font-normal text-muted-foreground">v{latest.version}, {latest.source === 'ollama' ? 'Ollama' : 'Copy-Paste'}</span></CardTitle></CardHeader>
      <CardContent><DeepAnalysisView data={data} flags={data.flags} /></CardContent>
    </Card>
  )
}

/** Which resume and cover letter versions I actually sent (brief §6.7). */
function VersionsSent({ application, onChange }: { application: Application; onChange: (body: Record<string, unknown>) => void }) {
  const docs = useDocuments(application.job_id)
  const of = (type: string) => (docs.data ?? []).filter((d) => d.type === type)
  const pick = (type: 'resume' | 'cover_letter', key: 'resume_version_id' | 'cover_letter_version_id') => (
    <Field label={type === 'resume' ? 'Resume sent' : 'Cover letter sent'}>
      <NativeSelect
        value={String(application[key] ?? '')}
        onChange={(v) => onChange({ [key]: v ? Number(v) : null })}
        options={[{ value: '', label: 'Not recorded' }, ...of(type).map((d) => ({ value: String(d.id), label: `v${d.version} (${new Date(d.created_at).toLocaleDateString('en-MY')})` }))]}
      />
    </Field>
  )
  return <div className="grid grid-cols-2 gap-3">{pick('resume', 'resume_version_id')}{pick('cover_letter', 'cover_letter_version_id')}</div>
}
