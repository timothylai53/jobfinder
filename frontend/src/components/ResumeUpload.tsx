import { useMutation } from '@tanstack/react-query'
import { FileUp } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { ResumeDraft } from '@/api/types'
import { cn } from '@/lib/utils'
import { ErrorText, Notice } from './common'
import ResumeReview from './ResumeReview'
import AiResumeParse from './ai/AiResumeParse'

/** Pick a PDF/DOCX -> parsed draft -> review screen. Calls onSaved after the bank is updated. */
export default function ResumeUpload({ onSaved }: { onSaved?: (msg: string) => void }) {
  const [draft, setDraft] = useState<ResumeDraft | null>(null)
  const [done, setDone] = useState('')
  const [dragging, setDragging] = useState(false)
  const [rev, setRev] = useState(0) // a new draft from the AI remounts the review screen
  const parse = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return api.post<ResumeDraft>('/api/resumes/parse', fd)
    },
    onSuccess: (d) => {
      setDraft(d)
      setDone('')
    },
  })

  if (draft)
    return (
      <div className="flex flex-col gap-3">
      <AiResumeParse draft={draft} onDraft={(d) => { setDraft(d); setRev(rev + 1) }} />
      <ResumeReview
        key={draft.file_path + rev}
        draft={draft}
        onCancel={() => setDraft(null)}
        onSaved={(m) => {
          setDraft(null)
          setDone(m)
          onSaved?.(m)
        }}
      />
      </div>
    )

  return (
    <div className="flex flex-col gap-2">
      <label
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          const f = e.dataTransfer.files?.[0]
          if (f) parse.mutate(f)
        }}
        className={cn(
          'flex cursor-pointer items-center gap-4 rounded-lg border-2 border-dashed bg-card px-5 py-5 transition-colors hover:border-primary',
          dragging && 'border-primary bg-accent',
        )}
      >
        <FileUp className="size-7 shrink-0 text-primary" />
        <div className="flex-1">
          <div className="font-semibold">{parse.isPending ? 'Reading your resume…' : 'Upload your resume'}</div>
          <div className="text-sm text-muted-foreground">PDF or DOCX, up to 10 MB. Drop it here or click to choose. You review everything before it is saved.</div>
        </div>
        <input
          type="file"
          accept=".pdf,.docx"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) parse.mutate(f)
            e.target.value = ''
          }}
        />
      </label>
      <ErrorText error={parse.error} />
      {done && <Notice tone="ok">{done}</Notice>}
    </div>
  )
}
