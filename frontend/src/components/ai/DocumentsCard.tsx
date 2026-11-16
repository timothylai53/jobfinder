import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { Application, DeepAnalysisResult, DocumentRow, InterviewPrepResult } from '@/api/types'
import { ErrorText } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { formatDate } from '@/lib/score'
import { DOC_LABEL } from './AiTools'
import { DeepAnalysisView, InterviewPrepView } from './AnalysisViews'

const SOURCE: Record<string, string> = { copy_paste: 'Copy-Paste', ollama: 'Ollama', template: 'Template', manual: 'Manual' }

export function useDocuments(jobId: number) {
  return useQuery({ queryKey: ['documents', jobId], queryFn: () => api.get<DocumentRow[]>(`/api/jobs/${jobId}/documents`) })
}

/** All saved versions for this job: preview, PDF download, view analyses, delete. (Job Detail's Documents tab.) */
export default function DocumentsCard({ jobId, application }: { jobId: number; application: Application | null }) {
  const qc = useQueryClient()
  const docs = useDocuments(jobId)
  const [view, setView] = useState<DocumentRow | null>(null)
  const del = useMutation({
    mutationFn: (id: number) => api.del(`/api/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', jobId] }),
  })
  const sent = new Set([application?.resume_version_id, application?.cover_letter_version_id].filter(Boolean))
  const rows = docs.data ?? []
  return (
    <div className="flex flex-col gap-2">
      {rows.length === 0 && <p className="text-muted-foreground">No versions yet. Tailor a resume, or write a cover letter from the template.</p>}
      {rows.length > 0 && (
        <ul className="divide-y rounded-xl border bg-background">
          {rows.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
              <span className="font-medium">{DOC_LABEL[d.type]} v{d.version}</span>
              <span className="text-sm text-muted-foreground">{SOURCE[d.source]}, {formatDate(d.created_at)}</span>
              {d.type === 'deep_analysis' && <span className="text-sm text-muted-foreground">fit {(d.content as unknown as DeepAnalysisResult).overall_fit}/100</span>}
              {sent.has(d.id) && <span className="rounded bg-accent px-1.5 text-[13px] font-medium text-accent-foreground">sent with application</span>}
              <div className="ml-auto flex gap-1">
                {d.printable ? (
                  <>
                    <Button size="sm" variant="ghost" asChild><a href={`/api/documents/${d.id}/html`} target="_blank" rel="noreferrer"><Eye className="size-4" aria-hidden /> Preview</a></Button>
                    <Button size="sm" variant="ghost" asChild><a href={`/api/documents/${d.id}/pdf`} target="_blank" rel="noreferrer"><Download className="size-4" aria-hidden /> PDF</a></Button>
                  </>
                ) : (
                  <Button size="sm" variant="ghost" onClick={() => setView(d)}><Eye className="size-4" aria-hidden /> View</Button>
                )}
                <Button size="sm" variant="ghost" aria-label={`Delete ${DOC_LABEL[d.type]} v${d.version}`}
                  onClick={() => { if (confirm(`Delete ${DOC_LABEL[d.type]} v${d.version}?`)) del.mutate(d.id) }}><Trash2 className="size-4" aria-hidden /></Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <ErrorText error={docs.error || del.error} />
      {view && (
        <Dialog open onOpenChange={(o) => { if (!o) setView(null) }}>
          <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
            <DialogHeader><DialogTitle>{DOC_LABEL[view.type]} v{view.version}</DialogTitle></DialogHeader>
            {view.type === 'deep_analysis'
              ? <DeepAnalysisView data={view.content as unknown as DeepAnalysisResult} flags={(view.content as unknown as DeepAnalysisResult).flags} />
              : <InterviewPrepView data={view.content as unknown as InterviewPrepResult} flags={(view.content as unknown as InterviewPrepResult).flags} />}
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
