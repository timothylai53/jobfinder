import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ClipboardPaste, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { PasteDraft } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { titlesMatch } from '@/lib/titles'
import { ErrorText, Notice } from './common'

interface Props {
  jobId: number
  title: string
  url?: string
  size?: 'sm' | 'default'
}

/**
 * For a "Summary only" job: open its posting in my browser, then paste the page here.
 * The paste updates THIS job (description, blank fields, filters, rescore); it never creates a new job.
 */
export default function PasteFullJdDialog({ jobId, title, url, size = 'default' }: Props) {
  const [open, setOpen] = useState(false)
  const [pasted, setPasted] = useState('')
  const [draft, setDraft] = useState<PasteDraft | null>(null)
  const [description, setDescription] = useState('')
  const qc = useQueryClient()

  const reset = () => { setPasted(''); setDraft(null); setDescription('') }

  const parse = useMutation({
    mutationFn: (text: string) => api.post<PasteDraft>('/api/jobs/parse-paste', { text }),
    onSuccess: (d) => { setDraft(d); setDescription(d.description) },
  })

  const update = useMutation({
    mutationFn: () => api.post<{ ok: boolean; score: number | null }>(`/api/jobs/${jobId}/full-description`, {
      description,
      location: draft?.location ?? '',
      salary_min: draft?.salary_min ?? null,
      salary_max: draft?.salary_max ?? null,
      salary_currency: draft?.salary_currency ?? '',
      job_type: draft?.job_type ?? '',
      work_arrangement: draft?.work_arrangement ?? '',
    }),
    onSuccess: () => {
      for (const key of [['job', String(jobId)], ['jobs'], ['dashboard'], ['applications']]) qc.invalidateQueries({ queryKey: key })
      setOpen(false)
      reset()
    },
  })

  const start = () => {
    if (url) window.open(url, '_blank', 'noopener,noreferrer')
    setOpen(true)
  }
  const mismatch = draft && draft.title && !titlesMatch(draft.title, title)

  return (
    <>
      <Button size={size} onClick={start}>
        <ExternalLink className="size-4" /> Open &amp; paste full JD
      </Button>
      <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset() }}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle className="text-xl">Paste the full job description</DialogTitle>
            <DialogDescription className="text-[15px]">
              {url ? 'The posting opened in your browser. ' : ''}
              On the job page, press Ctrl+A then Ctrl+C, and paste it here. This updates “{title}” and rescores it.
            </DialogDescription>
          </DialogHeader>

          {!draft ? (
            <div className="flex flex-col gap-3">
              <div className="relative">
                <Textarea
                  autoFocus
                  aria-label="Paste the job page"
                  rows={12}
                  value={pasted}
                  placeholder="Paste the job page here"
                  className="min-h-56 text-[15px]"
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
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {mismatch && (
                <Notice tone="warn">
                  The pasted page looks like “{draft.title}”, not “{title}”. Check it's the right job before updating.
                </Notice>
              )}
              <label className="flex flex-col gap-1">
                <span className="text-sm font-medium text-muted-foreground">
                  Job description{draft.removed_lines > 0 && `: ${draft.removed_lines} lines of page noise removed`}
                </span>
                <Textarea rows={14} value={description} onChange={(e) => setDescription(e.target.value)} className="text-[14px]" />
              </label>
              <p className="text-xs text-muted-foreground">
                Salary, job type, location and work arrangement found in the paste only fill fields that are still empty.
              </p>
              <div className="flex items-center justify-between gap-2">
                <Button variant="ghost" onClick={() => setDraft(null)}>Back to paste</Button>
                <div className="flex items-center gap-2">
                  <ErrorText error={update.error} />
                  <Button disabled={!description.trim() || update.isPending} onClick={() => update.mutate()}>
                    {update.isPending ? 'Updating…' : 'Update this job and rescore'}
                  </Button>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
