import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api } from '@/api/client'
import type { Application, DeepAnalysisResult, DocumentRow, InterviewPrepResult } from '@/api/types'
import { ErrorText } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { formatDate } from '@/lib/score'
import { DOC_LABEL } from './AiTools'
import { DeepAnalysisView, InterviewPrepView } from './AnalysisViews'

const SOURCE: Record<string, string> = { copy_paste: 'Copy-Paste', ollama: 'Ollama', template: 'Template', manual: 'Manual' }

export function useDocuments(jobId: number) {
  return useQuery({ queryKey: ['documents', jobId], queryFn: () => api.get<DocumentRow[]>(`/api/jobs/${jobId}/documents`) })
}

/** All saved versions for this job: preview, PDF download, view analyses, delete. */
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
    <Card>
      <CardHeader><CardTitle>Documents</CardTitle></CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {rows.length === 0 && <p className="text-sm text-muted-foreground">No versions yet. Use the AI tools or the template cover letter.</p>}
        {rows.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center gap-2 rounded-md border px-2 py-1.5 text-sm">
            <span className="font-medium">{DOC_LABEL[d.type]} v{d.version}</span>
            <span className="text-muted-foreground">{SOURCE[d.source]} · {formatDate(d.created_at)}</span>
            {d.type === 'deep_analysis' && <span className="rounded bg-muted px-1 text-xs">fit {(d.content as unknown as DeepAnalysisResult).overall_fit}</span>}
            {sent.has(d.id) && <span className="rounded bg-accent px-1.5 text-xs font-medium text-accent-foreground">sent with application</span>}
            <div className="ml-auto flex gap-1">
              {d.printable ? (
                <>
                  <Button size="sm" variant="ghost" asChild><a href={`/api/documents/${d.id}/html`} target="_blank" rel="noreferrer"><Eye className="size-4" /> Preview</a></Button>
                  <Button size="sm" variant="ghost" asChild><a href={`/api/documents/${d.id}/pdf`} target="_blank" rel="noreferrer"><Download className="size-4" /> PDF</a></Button>
                </>
              ) : (
                <Button size="sm" variant="ghost" onClick={() => setView(d)}><Eye className="size-4" /> View</Button>
              )}
              <Button size="sm" variant="ghost" aria-label={`Delete ${DOC_LABEL[d.type]} v${d.version}`}
                onClick={() => { if (confirm(`Delete ${DOC_LABEL[d.type]} v${d.version}?`)) del.mutate(d.id) }}><Trash2 className="size-4" /></Button>
            </div>
          </div>
        ))}
        <ErrorText error={docs.error || del.error} />
      </CardContent>
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
    </Card>
  )
}
