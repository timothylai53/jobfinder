import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Download, ExternalLink, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '@/api/client'
import { STATUSES, type Application, type DeepAnalysisResult, type DocumentRow, type JobDetail as JobDetailT, type Profile, type Status } from '@/api/types'
import Breakdown from '@/components/Breakdown'
import { AiActions, AiDialogs } from '@/components/ai/AiTools'
import { useAiDialog, useAiSettings, useDocuments } from '@/components/ai/hooks'
import DocumentsCard from '@/components/ai/DocumentsCard'
import { DeepAnalysisView } from '@/components/ai/AnalysisViews'
import PasteFullJdDialog from '@/components/PasteFullJdDialog'
import ProfileGaps from '@/components/ProfileGaps'
import { useToast } from '@/lib/toast'
import { ErrorText, Field, NativeSelect, Notice, ScoreBadge, StatusMark } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { formatDate, formatDateTime, formatSalary } from '@/lib/score'
import { gapNote, gaps, missingTitle, primaryStep, scoreVerdict } from '@/lib/verdict'
import { pendingDeletes } from '@/lib/pendingDeletes'
import { safeHttpUrl } from '@/lib/url'
import { cn } from '@/lib/utils'
import { useLocalCopy } from '@/lib/hooks'

const TABS = [['overview', 'Overview'], ['score', 'Score details'], ['documents', 'Documents'], ['description', 'Job description']] as const

const today = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD in local time

/** Remembers (in this browser only) that a resume version's PDF was downloaded, so the next step can be "Mark as applied". */
function useDownloaded(docId: number | undefined) {
  const key = docId ? `jobfinder.downloaded.${docId}` : ''
  const read = () => { try { return !!key && localStorage.getItem(key) === '1' } catch { return false } }
  const [done, setDone] = useState(read)
  // Another resume version: read its own flag (adjusted while rendering, not in an effect).
  const [seenKey, setSeenKey] = useState(key)
  if (key !== seenKey) {
    setSeenKey(key)
    setDone(read())
  }
  const mark = () => { try { if (key) localStorage.setItem(key, '1') } catch { /* storage blocked */ } setDone(true) }
  return [done, mark] as const
}

export default function JobDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const imported = (location.state as { imported?: { duplicate: boolean; hidden: boolean; hidden_reason: string } } | null)?.imported
  const q = useQuery({ queryKey: ['job', id], queryFn: () => api.get<JobDetailT>(`/api/jobs/${id}`) })
  const invalidate = () => {
    for (const k of [['job', id], ['jobs'], ['applications'], ['dashboard']]) qc.invalidateQueries({ queryKey: k })
  }
  const save = useMutation({ mutationFn: () => api.post('/api/applications', { job_id: Number(id) }), onSuccess: invalidate })
  const patchApp = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch(`/api/applications/${q.data!.application!.id}`, body),
    onSuccess: invalidate,
  })
  const toast = useToast()
  const hide = useMutation({
    mutationFn: (hidden: boolean) => api.patch(`/api/jobs/${id}`, { hidden }),
    onSuccess: (_d, hidden) => {
      invalidate()
      if (hidden) toast({ message: 'Job hidden.', undo: () => { api.patch(`/api/jobs/${id}`, { restore: true }).then(invalidate) } })
    },
  })
  // Delete waits 5 s for Undo before it really happens; the job leaves the list straight away.
  const remove = () => {
    const jobId = Number(id)
    pendingDeletes.add(jobId)
    navigate('/jobs')
    toast({
      message: 'Job deleted.',
      undo: () => pendingDeletes.remove(jobId),
      onExpire: () => { api.del(`/api/jobs/${jobId}`).finally(() => { invalidate(); pendingDeletes.remove(jobId) }) },
    })
  }
  const dialog = useAiDialog()
  // The open tab lives in the URL (?tab=score), so links, reloads and Back keep it.
  const [params, setParams] = useSearchParams()
  const tab = TABS.some(([v]) => v === params.get('tab')) ? params.get('tab')! : 'overview'

  if (q.isLoading) return <p className="text-muted-foreground">Loading…</p>
  if (q.error || !q.data) return <ErrorText error={q.error ?? 'Not found'} />
  const { job, match, application, history, summary_only: summaryOnly, low_confidence: lowConfidence } = q.data
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency)
  const verdict = match ? scoreVerdict(match.breakdown, { summaryOnly, lowConfidence }) : null
  const jobInfo = { id: job.id, title: job.title, summaryOnly, lowConfidence }

  return (
    <div className="flex flex-col gap-6">
      <Link to="/jobs" className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden /> Jobs
      </Link>

      <header className="flex flex-wrap items-start gap-x-6 gap-y-4">
        <ScoreBadge size="lg" score={match?.total ?? null} gated={(match?.gate_flags.length ?? 0) > 0} rough={summaryOnly || !!lowConfidence} />
        <div className="min-w-0 flex-1 basis-96">
          <h1 className="text-[28px] leading-tight font-semibold text-balance">{job.title}</h1>
          <p className="mt-0.5 text-[15px] text-muted-foreground">
            {[job.company, job.work_arrangement ? `${job.location} (${job.work_arrangement})` : job.location, salary, job.job_type].filter(Boolean).join(', ')}
          </p>
          {verdict && <p className={cn('mt-3 max-w-[65ch] text-[17px] leading-snug', verdict.tone === 'blocked' && 'text-danger')}>{verdict.text}</p>}
        </div>
        <div className="flex flex-col items-end gap-2">
          <PrimaryAction application={application} jobId={job.id} onSave={() => save.mutate()} saving={save.isPending}
            onTailor={() => dialog.start('tailor_resume')} onApplied={(body) => patchApp.mutate(body)} />
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => hide.mutate(!job.hidden)}>{job.hidden ? 'Unhide' : 'Hide'}</Button>
            <Button size="sm" variant="ghost" className="text-danger hover:bg-danger-bg hover:text-danger" onClick={remove}>Delete</Button>
          </div>
        </div>
      </header>

      <ErrorText error={save.error || patchApp.error || hide.error} />
      {imported?.duplicate && <Notice tone="warn">This ad matched a job already saved, so it was merged into that job.</Notice>}
      {job.hidden && <Notice tone="warn">Hidden: {job.hidden_reason}</Notice>}
      {summaryOnly && (
        <Notice tone="warn">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>Only the search summary was saved, so this score is a rough estimate and won't trigger a high-match alert. Open the posting, copy the page and paste it here.</span>
            <PasteFullJdDialog jobId={job.id} title={job.title} url={safeHttpUrl(job.urls[0]) ?? undefined} size="sm" />
          </div>
        </Notice>
      )}
      {!summaryOnly && lowConfidence && (
        <Notice tone="warn">{lowConfidence}. The score is capped at 50 and won't trigger a high-match alert. Check the job description yourself.</Notice>
      )}
      <ProfileGaps context="score" />

      <Tabs value={tab} onValueChange={(v) => setParams(v === 'overview' ? {} : { tab: v }, { replace: true })} className="gap-5">
        <TabsList variant="line" className="relative h-auto w-full justify-start gap-1 overflow-x-auto rounded-none border-b p-0">
          {TABS.map(([v, label]) => (
            <TabsTrigger key={v} value={v} className="h-auto flex-none rounded-none px-3 py-2 text-[15px]">{label}</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview" className="grid gap-x-12 gap-y-8 lg:grid-cols-2">
          <section aria-labelledby="missing">
            <h2 id="missing" className="mb-3 text-lg font-semibold">{match ? missingTitle(match.breakdown) : "What you're missing"}</h2>
            {!match ? <p className="text-muted-foreground">Not scored yet.</p> : <Missing breakdown={match.breakdown} onChanged={invalidate} />}
          </section>
          <div className="flex flex-col gap-8">
            <section aria-labelledby="application">
              <h2 id="application" className="mb-3 text-lg font-semibold">Application</h2>
              {application
                ? <ApplicationForm application={application} history={history} onPatch={(b) => patchApp.mutate(b)} />
                : <p className="text-muted-foreground">Not in your tracker yet. Use Save to tracker above.</p>}
            </section>
            <section aria-labelledby="ai-tools">
              <h2 id="ai-tools" className="mb-1 text-lg font-semibold">Resume and letters</h2>
              <p className="mb-3 text-sm text-muted-foreground">Written only from your Experience Bank; anything else is flagged before you save.</p>
              <AiActions dialog={dialog} showTailor={false} />
            </section>
          </div>
        </TabsContent>

        <TabsContent value="score" className="flex max-w-4xl flex-col gap-8">
          {match ? <Breakdown data={match.breakdown} /> : <p className="text-muted-foreground">Not scored yet.</p>}
          <LatestAnalysis jobId={job.id} />
        </TabsContent>

        <TabsContent value="documents" className="max-w-4xl">
          <DocumentsCard jobId={job.id} application={application} />
        </TabsContent>

        <TabsContent value="description" className="max-w-[75ch]">
          <p className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span>Added {formatDate(job.fetched_at)} from {job.sources.join(', ')}</span>
            {job.urls.map(safeHttpUrl).filter((u): u is string => !!u).map((u) => (
              <a key={u} href={u} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-foreground underline underline-offset-2">
                Open posting <ExternalLink className="size-3.5" aria-hidden />
              </a>
            ))}
          </p>
          <pre className="whitespace-pre-wrap font-sans text-[15px] leading-relaxed">{job.description}</pre>
        </TabsContent>
      </Tabs>

      <AiDialogs job={jobInfo} dialog={dialog} />
    </div>
  )
}

/** The one next step for this job: Save to tracker → Tailor resume → Download resume → Mark as applied. */
function PrimaryAction({ application, jobId, onSave, saving, onTailor, onApplied }: {
  application: Application | null; jobId: number; onSave: () => void; saving: boolean; onTailor: () => void
  onApplied: (body: Record<string, unknown>) => void
}) {
  const docs = useDocuments(jobId)
  const ai = useAiSettings()
  const resume = (docs.data ?? []).filter((d) => d.type === 'resume').sort((a, b) => b.version - a.version)[0] as DocumentRow | undefined
  const [downloaded, markDownloaded] = useDownloaded(resume?.id)
  const step = primaryStep({ tracked: !!application, status: application?.status, hasResume: !!resume, downloaded })

  if (step === 'save') return <Button size="lg" onClick={onSave} disabled={saving}>Save to tracker</Button>
  if (step === 'tailor') {
    return ai.data?.mode === 'off'
      ? <Button size="lg" asChild><Link to="/settings?section=ai">Turn on AI to tailor a resume</Link></Button>
      : <Button size="lg" onClick={onTailor}>Tailor resume</Button>
  }
  if (step === 'download' && resume) {
    return (
      <Button size="lg" asChild>
        <a href={`/api/documents/${resume.id}/pdf`} target="_blank" rel="noreferrer" onClick={markDownloaded}>
          <Download className="size-4" aria-hidden /> Download resume v{resume.version}
        </a>
      </Button>
    )
  }
  if (step === 'mark_applied' && resume && application) {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button size="lg" onClick={() => onApplied({ status: 'Applied', applied_at: today(), resume_version_id: application.resume_version_id ?? resume.id })}>
          Mark as applied
        </Button>
        <a href={`/api/documents/${resume.id}/pdf`} target="_blank" rel="noreferrer" className="text-sm text-muted-foreground underline underline-offset-2">
          Download resume v{resume.version} again
        </a>
      </div>
    )
  }
  return (
    <p className="text-right text-[15px]">
      <span className="font-medium">{application?.status}</span>
      {application?.applied_at && <span className="block text-sm text-muted-foreground">Applied {formatDate(application.applied_at)}</span>}
    </p>
  )
}

/** Only the partly met and missing items; the full breakdown is under Score details. A missing skill can be added to
 * the profile ("I have this"), which rescores every job; years and education are fixed in the profile instead. */
function Missing({ breakdown, onChanged }: { breakdown: Parameters<typeof gaps>[0]; onChanged: () => void }) {
  const qc = useQueryClient()
  const toast = useToast()
  const setSkills = async (change: (skills: string[]) => string[]) => {
    const p = await api.get<Profile>('/api/profile')
    await api.put('/api/profile', { ...p, skills: change(p.skills) })
    qc.invalidateQueries({ queryKey: ['profile'] })
    onChanged()
  }
  const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase()
  const add = useMutation({
    mutationFn: (skill: string) => setSkills((s) => (s.some((x) => same(x, skill)) ? s : [...s, skill])),
    onSuccess: (_d, skill) => toast({
      message: `${skill} added to your profile. Scores updated.`,
      undo: () => { setSkills((s) => s.filter((x) => !same(x, skill))) },
    }),
  })
  const claim = (skill: string) => {
    const ok = confirm(`Add "${skill}" to your profile skills?\n\nEvery job is rescored, and AI-written resumes may then mention ${skill}. Only add it if you really have it.`)
    if (ok) add.mutate(skill)
  }
  const list = gaps(breakdown)
  if (breakdown.gates.length === 0 && list.length === 0) {
    return <p className="flex items-center gap-2"><StatusMark status="met" /> You meet every requirement the ad lists.</p>
  }
  return (
    <>
      <ErrorText error={add.error} />
      <ul className="flex flex-col gap-2.5">
        {breakdown.gates.map((g) => (
          <li key={g.key} className="flex items-start gap-2.5 text-danger"><StatusMark status="not_met" className="mt-1" /><span className="font-medium">{g.message}</span></li>
        ))}
        {list.map(({ category, categoryKey, item }, i) => {
          const isSkill = categoryKey.endsWith('_skills') && item.status === 'not_met'
          const options = item.group && item.group.length > 0 ? item.group : [item.name]
          return (
            <li key={i} className="flex flex-wrap items-start gap-x-2.5 gap-y-1">
              <StatusMark status={item.status} className="mt-1" />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{item.name}</span>
                <span className="block text-sm text-muted-foreground">{gapNote(categoryKey, category, item.detail)}</span>
              </span>
              {isSkill && (
                <span className="flex flex-wrap gap-1">
                  {options.map((skill) => (
                    <Button key={skill} size="sm" variant="ghost" className="text-muted-foreground hover:text-foreground" disabled={add.isPending}
                      aria-label={`I have ${skill}: add it to my profile skills`} onClick={() => claim(skill)}>
                      <Plus className="size-4" aria-hidden /> {options.length > 1 ? `I have ${skill}` : 'I have this'}
                    </Button>
                  ))}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}

function ApplicationForm({ application, history, onPatch }: {
  application: Application; history: JobDetailT['history']; onPatch: (body: Record<string, unknown>) => void
}) {
  const [notes, setNotes] = useLocalCopy(application.notes ?? '')
  // Dates and the versions sent only mean something once you have applied.
  const applied = application.status !== 'Saved'
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(10.5rem,1fr))] gap-3">
        <Field label="Status">
          <NativeSelect className="h-9" value={application.status} onChange={(v) => onPatch({ status: v as Status })} options={[...STATUSES]} />
        </Field>
        {applied && (
          <>
            <Field label="Applied on">
              <Input type="date" value={application.applied_at ?? ''} onChange={(e) => onPatch({ applied_at: e.target.value || null })} />
            </Field>
            <Field label="Follow up on">
              <Input type="date" value={application.follow_up_at ?? ''} onChange={(e) => onPatch({ follow_up_at: e.target.value || null })} />
            </Field>
          </>
        )}
      </div>
      {applied && <VersionsSent application={application} onChange={onPatch} />}
      <Field label="Notes">
        <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== application.notes && onPatch({ notes })} />
      </Field>
      <details className="text-sm text-muted-foreground">
        <summary className="w-fit cursor-pointer select-none hover:text-foreground">Status history ({history.length})</summary>
        <ul className="mt-1.5 flex flex-col gap-0.5 pl-4">
          {history.map((h) => <li key={h.id}>{formatDateTime(h.changed_at)}: {h.from_status ?? 'new'} → {h.to_status}</li>)}
        </ul>
      </details>
    </div>
  )
}

/** The newest deep analysis, under the score breakdown (brief §7: Job Detail shows the deep analysis, if any). */
function LatestAnalysis({ jobId }: { jobId: number }) {
  const docs = useDocuments(jobId)
  const latest = (docs.data ?? []).find((d) => d.type === 'deep_analysis')
  if (!latest) return null
  const data = latest.content as unknown as DeepAnalysisResult
  return (
    <section aria-labelledby="deep" className="border-t pt-6">
      <h2 id="deep" className="mb-3 text-lg font-semibold">
        Deep analysis <span className="text-sm font-normal text-muted-foreground">v{latest.version}, {latest.source === 'ollama' ? 'Ollama' : 'Copy-Paste'}, {formatDate(latest.created_at)}</span>
      </h2>
      <DeepAnalysisView data={data} flags={data.flags} />
    </section>
  )
}

/** Which resume and cover letter versions I actually sent (brief §6.7). */
function VersionsSent({ application, onChange }: { application: Application; onChange: (body: Record<string, unknown>) => void }) {
  const docs = useDocuments(application.job_id)
  const of = (type: string) => (docs.data ?? []).filter((d) => d.type === type)
  const pick = (type: 'resume' | 'cover_letter', key: 'resume_version_id' | 'cover_letter_version_id') => (
    <Field label={type === 'resume' ? 'Resume sent' : 'Cover letter sent'}>
      <NativeSelect
        className="h-9"
        value={String(application[key] ?? '')}
        onChange={(v) => onChange({ [key]: v ? Number(v) : null })}
        options={[{ value: '', label: 'Not recorded' }, ...of(type).map((d) => ({ value: String(d.id), label: `v${d.version}, ${formatDate(d.created_at)}` }))]}
      />
    </Field>
  )
  return <div className="grid grid-cols-[repeat(auto-fit,minmax(12rem,1fr))] gap-3">{pick('resume', 'resume_version_id')}{pick('cover_letter', 'cover_letter_version_id')}</div>
}
