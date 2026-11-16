import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ClipboardPaste, Link2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/api/client'
import type { JobDraft, PasteDraft } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { isUrl } from '@/lib/url'
import { cn } from '@/lib/utils'
import { ErrorText } from './common'

const EMPTY: JobDraft = {
  title: '', company: '', location: '', work_arrangement: '', description: '', url: '',
  salary_min: null, salary_max: null, salary_currency: 'MYR', job_type: '',
}

type FieldState = 'found' | 'check' | 'fill' | 'undisclosed' | 'none'
const BADGE: Record<Exclude<FieldState, 'none'>, { text: string; cls: string }> = {
  found: { text: 'found in paste', cls: 'bg-accent text-accent-foreground' },
  check: { text: 'please check', cls: 'border border-attention-edge bg-attention-bg text-attention' },
  fill: { text: 'fill in', cls: 'bg-muted text-muted-foreground' },
  undisclosed: { text: 'not disclosed in ad', cls: 'bg-muted text-muted-foreground' },
}

function DetectedField({ label, state, children, className }: { label: string; state: FieldState; children: React.ReactNode; className?: string }) {
  return (
    <label className={cn('flex flex-col gap-1', className)}>
      <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm font-medium text-muted-foreground">
        <span className="whitespace-nowrap">{label}</span>
        {state !== 'none' && <span className={cn('rounded px-1.5 text-xs font-normal whitespace-nowrap', BADGE[state].cls)}>{BADGE[state].text}</span>}
      </span>
      {children}
    </label>
  )
}

/**
 * Import a job. Main path: paste the whole job page (Ctrl+A, Ctrl+C) and let the app pick out the fields.
 * A URL can be tried first; many job boards block it, in which case we go straight to pasting.
 */
export default function ImportJobDialog({ defaultOpen = false, variant = 'default' }: { defaultOpen?: boolean; variant?: 'default' | 'outline' }) {
  const [open, setOpen] = useState(defaultOpen)
  const [stage, setStage] = useState<'paste' | 'review'>('paste')
  const [pasted, setPasted] = useState('')
  const [url, setUrl] = useState('')
  const [tip, setTip] = useState('')
  const [form, setForm] = useState<JobDraft>(EMPTY)
  const [detected, setDetected] = useState<string[]>([])
  const [uncertain, setUncertain] = useState<string[]>([])
  const [salaryHidden, setSalaryHidden] = useState(false)
  const [removed, setRemoved] = useState(0)
  const pasteBox = useRef<HTMLTextAreaElement>(null)
  const qc = useQueryClient()
  const navigate = useNavigate()

  useEffect(() => { if (defaultOpen) setOpen(true) }, [defaultOpen])

  const reset = () => {
    setStage('paste'); setPasted(''); setUrl(''); setTip(''); setForm(EMPTY); setDetected([]); setUncertain([]); setSalaryHidden(false); setRemoved(0)
  }

  const parse = useMutation({
    mutationFn: (text: string) => api.post<PasteDraft>('/api/jobs/parse-paste', { text }),
    onSuccess: (d) => {
      // The URL field is only ever a real link: the one found in the paste, else a valid link typed above.
      setForm((f) => ({ ...EMPTY, url: d.url || (isUrl(f.url) ? f.url : isUrl(url) ? url.trim() : ''), title: d.title,
        company: d.company, location: d.location, work_arrangement: d.work_arrangement ?? "",
        salary_min: d.salary_min, salary_max: d.salary_max, salary_currency: d.salary_currency || 'MYR',
        job_type: d.job_type, description: d.description }))
      setDetected(d.detected)
      setUncertain(d.uncertain ?? [])
      setSalaryHidden(!!d.salary_undisclosed)
      setRemoved(d.removed_lines)
      setStage('review')
    },
  })

  const fetchUrl = useMutation({
    mutationFn: () => api.post<{ ok: boolean; error?: string; draft?: JobDraft }>('/api/jobs/fetch-url', { url }),
    onSuccess: (r) => {
      if (r.ok && r.draft) {
        const d = r.draft
        setForm({ ...EMPTY, ...d, salary_currency: d.salary_currency || 'MYR' })
        setDetected([d.title && 'title', d.company && 'company', d.location && 'location', d.salary_min && 'salary', d.job_type && 'job_type']
          .filter((k): k is string => !!k))
        setUncertain([])
        setRemoved(0)
        setStage('review')
      } else {
        setForm((f) => ({ ...f, url: isUrl(url) ? url.trim() : '' }))
        setTip('That site does not allow automatic fetching. Open the job in your browser, press Ctrl+A then Ctrl+C, and paste it below.')
        setTimeout(() => pasteBox.current?.focus(), 50)
      }
    },
  })

  const save = useMutation({
    mutationFn: () => api.post<{ id: number; duplicate: boolean; hidden: boolean; hidden_reason: string }>('/api/jobs/manual', form),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setOpen(false)
      reset()
      navigate(`/jobs/${r.id}`, { state: { imported: r } })
    },
  })

  const set = (k: keyof JobDraft) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const v = e.target.value
    setForm((f) => ({ ...f, [k]: k === 'salary_min' || k === 'salary_max' ? (v === '' ? null : Number(v)) : v }))
  }
  const state = (k: string): FieldState => (!detected.includes(k) ? 'fill' : uncertain.includes(k) ? 'check' : 'found')

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset() }}>
      <DialogTrigger asChild>
        <Button variant={variant}>Import job</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-xl">Import a job</DialogTitle>
          <DialogDescription className="text-[15px]">
            {stage === 'paste'
              ? 'On the job page, press Ctrl+A then Ctrl+C, and paste the whole page here. Menus, footers and “similar jobs” are removed for you.'
              : 'Check the fields we picked out, then import. Everything stays editable.'}
          </DialogDescription>
        </DialogHeader>

        {stage === 'paste' && (
          <div className="flex flex-col gap-4">
            {tip && <p className="rounded-lg border border-attention-edge bg-attention-bg px-3 py-2 text-[15px] text-attention">{tip}</p>}
            <div className="relative">
              <Textarea
                ref={pasteBox}
                autoFocus
                aria-label="Paste the job page"
                rows={13}
                value={pasted}
                placeholder="Paste the job page here"
                className="min-h-64 text-[15px]"
                onChange={(e) => setPasted(e.target.value)}
                onPaste={(e) => {
                  const text = e.clipboardData.getData('text')
                  if (text.trim()) {
                    e.preventDefault()
                    setPasted(text)
                    parse.mutate(text)
                  }
                }}
              />
              {!pasted && (
                <ClipboardPaste aria-hidden className="pointer-events-none absolute top-1/2 left-1/2 size-10 -translate-1/2 text-muted-foreground/40" />
              )}
            </div>
            <div className="flex items-center justify-between gap-2">
              <ErrorText error={parse.error} />
              <Button className="ml-auto" disabled={!pasted.trim() || parse.isPending} onClick={() => parse.mutate(pasted)}>
                {parse.isPending ? 'Reading…' : 'Read pasted text'}
              </Button>
            </div>
            <div className="flex flex-col gap-1.5 border-t pt-4">
              <span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground"><Link2 className="size-4" /> Or try a link</span>
              <div className="flex gap-2">
                <Input
                  placeholder="https://… (company career pages often work; JobStreet and LinkedIn block this)"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onPaste={(e) => {
                    const text = e.clipboardData.getData('text')
                    if (text.trim() && !isUrl(text)) {
                      // That's a page, not a link: treat it as a smart paste.
                      e.preventDefault()
                      setPasted(text)
                      parse.mutate(text)
                    }
                  }}
                />
                <Button variant="outline" disabled={!isUrl(url) || fetchUrl.isPending} onClick={() => fetchUrl.mutate()}>
                  {fetchUrl.isPending ? 'Fetching…' : 'Fetch'}
                </Button>
              </div>
              <ErrorText error={fetchUrl.error} />
            </div>
          </div>
        )}

        {stage === 'review' && (
          <form
            className="grid grid-cols-2 gap-3"
            onSubmit={(e) => {
              e.preventDefault()
              save.mutate()
            }}
          >
            <DetectedField label="Job title" state={state('title')} className="col-span-2">
              <Input required className="text-base font-semibold" value={form.title} onChange={set('title')} />
            </DetectedField>
            <DetectedField label="Company" state={state('company')}>
              <Input value={form.company} onChange={set('company')} />
            </DetectedField>
            <DetectedField label="Location" state={state('location')}>
              <Input value={form.location} onChange={set('location')} placeholder="e.g. Cyberjaya, or Remote" />
            </DetectedField>
            <DetectedField label="Salary (monthly, MYR)" state={salaryHidden && form.salary_min === null ? 'undisclosed' : state('salary')}>
              <div className="flex items-center gap-2">
                <Input type="number" aria-label="Salary min" placeholder="min" value={form.salary_min ?? ''} onChange={set('salary_min')} />
                <span className="text-muted-foreground">to</span>
                <Input type="number" aria-label="Salary max" placeholder="max" value={form.salary_max ?? ''} onChange={set('salary_max')} />
              </div>
            </DetectedField>
            <div className="grid grid-cols-[1fr_1.15fr] gap-3">
              <DetectedField label="Job type" state={state('job_type')}>
                <Input value={form.job_type} onChange={set('job_type')} placeholder="e.g. Full time" />
              </DetectedField>
              <DetectedField label="Work arrangement" state={form.work_arrangement ? state('work_arrangement') : 'none'}>
                <select
                  className="h-8 rounded-lg border border-input bg-background px-2 text-[15px]"
                  value={form.work_arrangement}
                  onChange={(e) => setForm((f) => ({ ...f, work_arrangement: e.target.value }))}
                >
                  <option value="">Not stated</option>
                  <option>On-site</option>
                  <option>Hybrid</option>
                  <option>Remote</option>
                </select>
              </DetectedField>
            </div>
            <DetectedField label="Job URL (optional)" state={form.url ? state('url') : 'none'} className="col-span-2">
              <Input type="url" value={form.url} onChange={set('url')} placeholder="https://…"
                aria-invalid={!!form.url && !isUrl(form.url)} />
            </DetectedField>
            <label className="col-span-2 flex flex-col gap-1">
              <span className="text-sm font-medium text-muted-foreground">
                Job description{removed > 0 && `: ${removed} lines of page noise removed`}
              </span>
              <Textarea required rows={12} value={form.description} onChange={set('description')} className="text-[14px]" />
            </label>
            <div className="col-span-2 flex items-center justify-between gap-2">
              <Button type="button" variant="ghost" onClick={() => setStage('paste')}>Back to paste</Button>
              <div className="flex items-center gap-2">
                <ErrorText error={save.error} />
                <Button type="submit" disabled={save.isPending || !form.title.trim() || !form.description.trim()}>
                  {save.isPending ? 'Importing…' : 'Import and score'}
                </Button>
              </div>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
