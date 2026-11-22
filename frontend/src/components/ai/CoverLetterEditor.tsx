import { useMutation } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { CoverLetterResult, DocumentRow, GuardFlag } from '@/api/types'
import { ErrorText, Field, FlagIcon } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { flagsAt } from '@/lib/ai'
import { cn } from '@/lib/utils'

/** Edit a cover letter (from AI or from the template), then save it as a new version. */
export default function CoverLetterEditor({ jobId, initial, flags = [], source, aiTaskId, onSaved }: {
  jobId: number
  initial: CoverLetterResult
  flags?: GuardFlag[]
  source: 'copy_paste' | 'ollama' | 'template'
  aiTaskId?: number
  onSaved: (d: DocumentRow) => void
}) {
  const [greeting, setGreeting] = useState(initial.greeting)
  const [paras, setParas] = useState(initial.paragraphs.map((text, i) => ({ text, flags: flagsAt(flags, `paragraphs.${i}`) })))
  const [closing, setClosing] = useState(initial.closing)
  const idFlags = flagsAt(flags, 'used_ids')
  const save = useMutation({
    mutationFn: () => api.post<DocumentRow>('/api/documents/cover-letter', {
      job_id: jobId, source, ai_task_id: aiTaskId ?? null, greeting, closing,
      paragraphs: paras.map((p) => p.text), used_ids: initial.used_ids,
    }),
    onSuccess: onSaved,
  })
  return (
    <div className="flex flex-col gap-3">
      <Field label="Greeting"><Input value={greeting} onChange={(e) => setGreeting(e.target.value)} /></Field>
      {paras.map((p, i) => (
        <div key={i} className="flex flex-col gap-1">
          <div className="flex items-start gap-2">
            <Textarea rows={4} value={p.text} aria-label={`Paragraph ${i + 1}`}
              onChange={(e) => setParas(paras.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
              className={cn('text-[15px]', p.flags.length && 'border-danger-edge bg-danger-bg/40')} />
            <Button variant="ghost" size="sm" aria-label={`Remove paragraph ${i + 1}`} onClick={() => setParas(paras.filter((_, j) => j !== i))}><Trash2 className="size-4" /></Button>
          </div>
          {p.flags.map((f, k) => <span key={k} className="text-sm text-danger"><FlagIcon />{f.message}</span>)}
        </div>
      ))}
      <Button variant="outline" size="sm" className="self-start" onClick={() => setParas([...paras, { text: '', flags: [] }])}><Plus className="size-4" /> Add paragraph</Button>
      <Field label="Closing"><Input value={closing} onChange={(e) => setClosing(e.target.value)} /></Field>
      <p className="text-sm text-muted-foreground">
        Based on bank items: {initial.used_ids.join(', ') || 'none'}. Your name and contact details are added from your profile.
      </p>
      {idFlags.map((f, k) => <span key={k} className="text-sm text-danger"><FlagIcon />{f.message}</span>)}
      <div className="flex items-center justify-end gap-2">
        <ErrorText error={save.error} />
        <Button disabled={save.isPending || !paras.some((p) => p.text.trim())} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : 'Save as new cover letter version'}
        </Button>
      </div>
    </div>
  )
}
