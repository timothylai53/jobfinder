import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, FileText, ListChecks, MessagesSquare, PenLine, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type {
  AiTask, AiTaskType, BaseResume, CoverLetterResult, DeepAnalysisResult, DocumentRow, ExperienceItem, InterviewPrepResult, TailorResult, TemplateDraft,
} from '@/api/types'
import { ErrorText, Field, NativeSelect, Notice } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { DOC_LABEL, TASK_LABEL } from '@/lib/ai'
import { defaultStartFrom, typeSummary } from '@/lib/baseResumes'
import { cn } from '@/lib/utils'
import AiTaskFlow from './AiTaskFlow'
import { type AiOpen, useAiDialog, useAiSettings } from './hooks'
import { DeepAnalysisView, InterviewPrepView } from './AnalysisViews'
import CoverLetterEditor from './CoverLetterEditor'
import TailorReview from './TailorReview'

function Saved({ doc, onClose }: { doc: DocumentRow; onClose: () => void }) {
  return (
    <Notice tone="ok">
      <div className="flex flex-wrap items-center gap-3">
        <span>Saved as <strong>{DOC_LABEL[doc.type]} v{doc.version}</strong>.</span>
        {doc.printable && <a className="underline" href={`/api/documents/${doc.id}/pdf`} target="_blank" rel="noreferrer">Download PDF</a>}
        {doc.printable && <a className="underline" href={`/api/documents/${doc.id}/docx`} download>Word (.docx)</a>}
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

export interface JobInfo { id: number; title: string; summaryOnly: boolean; lowConfidence: string }

/** Tailor resume, step 0: which items the AI may use. Defaults to the base resume used last (or the whole bank). */
function StartFrom({ usable, onStart, onCancel }: { usable: BaseResume[]; onStart: (id: number | null) => void; onCancel: () => void }) {
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const [choice, setChoice] = useState<string | null>(null)
  if (!bank.data) return <p className="text-sm text-muted-foreground">Loading…</p>
  const value = choice ?? String(defaultStartFrom(usable) ?? '')
  const picked = usable.find((r) => String(r.id) === value)
  const items = (bank.data ?? []).filter((i) => !picked || picked.item_ids.includes(i.id))
  return (
    <div className="flex flex-col gap-3">
      <Field label="Start from" className="max-w-md">
        <NativeSelect value={value} onChange={setChoice}
          options={[{ value: '', label: 'Whole bank' }, ...usable.map((r) => ({ value: String(r.id), label: r.name }))]} />
      </Field>
      <p className="text-sm text-muted-foreground">
        {picked ? `Only ${picked.name}'s ${items.length} items go to the AI (${typeSummary(items)}). You can still add any other bank item in the review.`
          : `All ${items.length} bank items go to the AI.`}
      </p>
      <div className="flex gap-2">
        <Button onClick={() => onStart(picked ? picked.id : null)}>Build prompt</Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  )
}

function TaskDialog({ task, job, provider, onClose }: { task: AiTaskType; job: JobInfo; provider: 'copy_paste' | 'ollama'; onClose: () => void }) {
  const qc = useQueryClient()
  const rough = (task === 'tailor_resume' || task === 'cover_letter') && (job.summaryOnly || !!job.lowConfidence)
  const [go, setGo] = useState(!rough)
  const [saved, setSaved] = useState<DocumentRow | null>(null)
  // Tailoring asks where to start (a base resume or the whole bank) before the prompt is built.
  const [base, setBase] = useState<{ id: number | null } | null>(null)
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => api.get<BaseResume[]>('/api/resumes'), enabled: task === 'tailor_resume' })
  const usable = (resumes.data ?? []).filter((r) => r.item_ids.length > 0)
  // With no base resume that has items there is nothing to choose: the whole bank is used straight away.
  const choosing = task === 'tailor_resume' && !base && (!resumes.data || usable.length > 0)
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
        ) : choosing ? (
          resumes.data ? <StartFrom usable={usable} onStart={(id) => setBase({ id })} onCancel={onClose} />
            : <ErrorText error={resumes.error} />
        ) : (
          <AiTaskFlow task={task} jobId={job.id} provider={provider} baseResumeId={base?.id ?? null}>
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

const MORE: { open: AiOpen & string; label: string; icon: typeof Sparkles; ai: boolean }[] = [
  { open: 'deep_analysis', label: TASK_LABEL.deep_analysis, icon: ListChecks, ai: true },
  { open: 'cover_letter', label: TASK_LABEL.cover_letter, icon: PenLine, ai: true },
  { open: 'interview_prep', label: TASK_LABEL.interview_prep, icon: MessagesSquare, ai: true },
  { open: 'template', label: 'Cover letter from template (no AI)', icon: FileText, ai: false },
]


/** The open dialog. The mode (Copy-Paste or Ollama) is the one chosen in Settings -> AI; if Ollama fails, the
 * dialog itself offers Copy-Paste for that task. */
export function AiDialogs({ job, dialog }: { job: JobInfo; dialog: ReturnType<typeof useAiDialog> }) {
  const settings = useAiSettings()
  const mode = settings.data?.mode ?? 'copy_paste'
  const provider = (mode === 'off' ? 'copy_paste' : mode) as 'copy_paste' | 'ollama'
  if (dialog.open === 'template') return <TemplateDialog key={dialog.n} job={job} onClose={dialog.close} />
  if (dialog.open) return <TaskDialog key={dialog.n} task={dialog.open} job={job} provider={provider} onClose={dialog.close} />
  return null
}

/** The AI actions on Job Detail. With `showTailor` off (the page's primary button already offers it), "Tailor resume"
 * moves into the More menu so a new version is always one click away, but never shown twice. */
export function AiActions({ dialog, showTailor = true }: { dialog: ReturnType<typeof useAiDialog>; showTailor?: boolean }) {
  const settings = useAiSettings()
  const off = settings.data?.mode === 'off'
  const tailor = { open: 'tailor_resume' as const, label: 'Tailor resume (new version)', icon: FileText, ai: true }
  const items = [...(showTailor ? [] : [tailor]), ...MORE].filter((m) => !off || !m.ai)
  return (
    <div className="flex flex-wrap items-center gap-2">
      {!off && showTailor && (
        <Button onClick={() => dialog.start('tailor_resume')}>
          <FileText className="size-4" aria-hidden /> Tailor resume
        </Button>
      )}
      <MoreMenu items={items} label="More" onPick={(o) => dialog.start(o)} />
      {off && (
        <span className="text-sm text-muted-foreground">
          AI is off (<Link to="/settings?section=ai" className="underline underline-offset-2">Settings → AI</Link>). The template cover letter still works.
        </span>
      )}
    </div>
  )
}

/** A small disclosure menu: Escape or a click outside closes it, and focus returns to the button. */
function MoreMenu({ items, label, onPick }: { items: typeof MORE; label: string; onPick: (o: AiOpen) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); button.current?.focus() } }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open])
  return (
    <div ref={ref} className="relative">
      <Button ref={button} variant="outline" aria-expanded={open} aria-controls="ai-more" onClick={() => setOpen(!open)}>
        {label} <ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} aria-hidden />
      </Button>
      {open && (
        <ul id="ai-more" className="absolute right-0 z-40 mt-1 w-72 rounded-lg border bg-popover p-1 shadow-pop">
          {items.map(({ open: o, label, icon: Icon }) => (
            <li key={o}>
              <button type="button" className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-[15px] hover:bg-muted focus-visible:bg-muted"
                onClick={() => { setOpen(false); onPick(o) }}>
                <Icon className="size-4 text-muted-foreground" aria-hidden /> {label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
