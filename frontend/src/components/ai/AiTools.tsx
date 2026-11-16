import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, ListChecks, MessagesSquare, PenLine, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type {
  AiTask, AiTaskType, CoverLetterResult, DeepAnalysisResult, DocumentRow, ExperienceItem, InterviewPrepResult, TailorResult, TemplateDraft,
} from '@/api/types'
import { ErrorText, NativeSelect, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { TASK_LABEL } from '@/lib/ai'
import AiTaskFlow, { useAiSettings } from './AiTaskFlow'
import { DeepAnalysisView, InterviewPrepView } from './AnalysisViews'
import CoverLetterEditor from './CoverLetterEditor'
import TailorReview from './TailorReview'

export const DOC_LABEL: Record<string, string> = {
  resume: 'Resume', cover_letter: 'Cover letter', deep_analysis: 'Deep analysis', interview_prep: 'Interview prep',
}

function Saved({ doc, onClose }: { doc: DocumentRow; onClose: () => void }) {
  return (
    <Notice tone="ok">
      <div className="flex flex-wrap items-center gap-3">
        <span>Saved as <strong>{DOC_LABEL[doc.type]} v{doc.version}</strong>.</span>
        {doc.printable && <a className="underline" href={`/api/documents/${doc.id}/pdf`} target="_blank" rel="noreferrer">Download PDF</a>}
        {doc.printable && <a className="underline" href={`/api/documents/${doc.id}/html`} target="_blank" rel="noreferrer">Preview</a>}
        <Button size="sm" variant="outline" className="ml-auto" onClick={onClose}>Close</Button>
      </div>
    </Notice>
  )
}

function SaveResult({ task, onSaved, children }: { task: AiTask; onSaved: (d: DocumentRow) => void; children: React.ReactNode }) {
  const save = useMutation({ mutationFn: () => api.post<DocumentRow>('/api/documents/from-task', { ai_task_id: task.id }), onSuccess: onSaved })
  return (
    <div className="flex flex-col gap-3">
      {children}
      <div className="flex items-center justify-end gap-2">
        <ErrorText error={save.error} />
        <Button onClick={() => save.mutate()} disabled={save.isPending || task.status === 'saved'}>{save.isPending ? 'Saving…' : 'Save as new version'}</Button>
      </div>
    </div>
  )
}

interface JobInfo { id: number; title: string; summaryOnly: boolean; lowConfidence: string }

function TaskDialog({ task, job, provider, onClose }: { task: AiTaskType; job: JobInfo; provider: 'copy_paste' | 'ollama'; onClose: () => void }) {
  const qc = useQueryClient()
  const rough = (task === 'tailor_resume' || task === 'cover_letter') && (job.summaryOnly || !!job.lowConfidence)
  const [go, setGo] = useState(!rough)
  const [saved, setSaved] = useState<DocumentRow | null>(null)
  const done = (d: DocumentRow) => {
    setSaved(d)
    for (const k of [['documents', job.id], ['job', String(job.id)]]) qc.invalidateQueries({ queryKey: k })
  }
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="text-xl">{TASK_LABEL[task]}: {job.title}</DialogTitle>
          <DialogDescription className="text-[15px]">
            {provider === 'ollama' ? 'Runs on Ollama on this laptop; nothing leaves your computer. If Ollama can’t, you can switch this task to Copy-Paste.' : 'Copy the prompt into a free web chat yourself, then paste the reply back. Nothing is sent automatically.'}
          </DialogDescription>
        </DialogHeader>
        {!go ? (
          <Notice tone="warn">
            <div className="flex flex-col gap-2">
              <span>
                <strong>Careful:</strong> {job.summaryOnly
                  ? 'only the search summary of this job is saved, not the full job description.'
                  : `this job's score is low confidence (${job.lowConfidence}).`}{' '}
                A {task === 'tailor_resume' ? 'tailored resume' : 'cover letter'} built from it may miss what the job really asks for.
                {job.summaryOnly && ' Use “Open & paste full JD” on this page first if you can.'}
              </span>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => setGo(true)}>Continue anyway</Button>
                <Button size="sm" variant="outline" onClick={onClose}>Cancel</Button>
              </div>
            </div>
          </Notice>
        ) : saved ? (
          <Saved doc={saved} onClose={onClose} />
        ) : (
          <AiTaskFlow task={task} jobId={job.id} provider={provider}>
            {(t) =>
              task === 'tailor_resume' ? <TailorReview task={t as unknown as AiTask<TailorResult>} onSaved={done} />
              : task === 'cover_letter' ? <CoverLetterEditor jobId={job.id} initial={t.result as unknown as CoverLetterResult} flags={t.flags} source={t.provider} aiTaskId={t.id} onSaved={done} />
              : task === 'deep_analysis' ? <SaveResult task={t} onSaved={done}><DeepAnalysisView data={t.result as unknown as DeepAnalysisResult} flags={t.flags} /></SaveResult>
              : <SaveResult task={t} onSaved={done}><InterviewPrepView data={t.result as unknown as InterviewPrepResult} flags={t.flags} /></SaveResult>
            }
          </AiTaskFlow>
        )}
      </DialogContent>
    </Dialog>
  )
}

/** Cover letter template mode: fill-in-the-blanks from the job, top matched skills and 1-2 bank items. No AI. */
function TemplateDialog({ job, onClose }: { job: JobInfo; onClose: () => void }) {
  const qc = useQueryClient()
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const [codes, setCodes] = useState<string[] | null>(null)
  const draft = useQuery({
    queryKey: ['cover-template', job.id, codes],
    queryFn: () => api.post<TemplateDraft>('/api/documents/cover-letter/template-draft', { job_id: job.id, item_codes: codes }),
  })
  const [saved, setSaved] = useState<DocumentRow | null>(null)
  const chosen = codes ?? draft.data?.used_ids ?? []
  const items = (bank.data ?? []).filter((b) => ['work', 'project', 'achievement'].includes(b.type))
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-xl">Cover letter from template: {job.title}</DialogTitle>
          <DialogDescription className="text-[15px]">Filled in from the job, your top matched skills and up to 2 bank items. No AI involved; edit freely.</DialogDescription>
        </DialogHeader>
        {saved ? <Saved doc={saved} onClose={onClose} /> : (
          <>
            <div className="flex flex-col gap-1 text-sm">
              <span className="font-medium">Bank items to mention (up to 2)</span>
              {items.map((b) => (
                <label key={b.code} className="flex items-center gap-2">
                  <input type="checkbox" checked={chosen.includes(b.code)} disabled={!chosen.includes(b.code) && chosen.length >= 2}
                    onChange={(e) => setCodes(e.target.checked ? [...chosen, b.code] : chosen.filter((c) => c !== b.code))} />
                  [{b.code}] {b.title}{b.organization && `, ${b.organization}`}
                </label>
              ))}
            </div>
            <ErrorText error={draft.error} />
            {draft.data && (
              <CoverLetterEditor key={JSON.stringify(draft.data.paragraphs)} jobId={job.id} initial={draft.data} source="template"
                onSaved={(d) => { setSaved(d); qc.invalidateQueries({ queryKey: ['documents', job.id] }) }} />
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

const ACTIONS: { task: AiTaskType; icon: typeof Sparkles }[] = [
  { task: 'deep_analysis', icon: ListChecks },
  { task: 'tailor_resume', icon: FileText },
  { task: 'cover_letter', icon: PenLine },
  { task: 'interview_prep', icon: MessagesSquare },
]

/** Job Detail: AI actions (Copy-Paste or Ollama, overridable per action) + the template cover letter. */
export default function AiTools({ job }: { job: JobInfo }) {
  const settings = useAiSettings()
  const mode = settings.data?.mode ?? 'copy_paste'
  const [override, setOverride] = useState<'copy_paste' | 'ollama' | ''>('')
  const [open, setOpen] = useState<AiTaskType | 'template' | null>(null)
  const [n, setN] = useState(0) // a fresh task every time a dialog opens
  const provider = (override || (mode === 'off' ? 'copy_paste' : mode)) as 'copy_paste' | 'ollama'
  const start = (t: AiTaskType | 'template') => { setN(n + 1); setOpen(t) }
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Sparkles className="size-4" /> AI tools</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {mode === 'off' ? (
          <p className="text-sm text-muted-foreground">AI is off (<Link to="/settings?section=ai" className="underline">Settings → AI</Link>). The template cover letter still works.</p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {ACTIONS.map(({ task, icon: Icon }) => (
                <Button key={task} variant="outline" onClick={() => start(task)}><Icon className="size-4" /> {TASK_LABEL[task]}</Button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              Use
              <NativeSelect value={override || mode} onChange={(v) => setOverride(v as 'copy_paste' | 'ollama')}
                options={[{ value: 'copy_paste', label: 'Copy-Paste (free web chat)' }, { value: 'ollama', label: 'Ollama (on this laptop)' }]} />
              for these actions
            </label>
          </>
        )}
        <Button variant="ghost" className="self-start" onClick={() => start('template')}><PenLine className="size-4" /> Cover letter from template (no AI)</Button>
      </CardContent>
      {open === 'template' && <TemplateDialog key={n} job={job} onClose={() => setOpen(null)} />}
      {open && open !== 'template' && <TaskDialog key={n} task={open} job={job} provider={provider} onClose={() => setOpen(null)} />}
    </Card>
  )
}
