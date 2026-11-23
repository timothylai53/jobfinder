import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '@/api/client'
import { ErrorText } from '@/components/common'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/score'
import { useToast } from '@/lib/toast'

interface BackupRow { name: string; kind: 'automatic' | 'manual' | 'before restore'; size: number; created_at: string }

const SHOWN = 8
const size = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)

/** Settings → Export & backup: every backup, newest first, each with "Restore…". */
export default function BackupList() {
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['backups'], queryFn: () => api.get<BackupRow[]>('/api/backups') })
  const [all, setAll] = useState(false)
  const restore = useMutation({
    mutationFn: (b: BackupRow) => api.post<{ saved_current_as: string }>(`/api/backups/${encodeURIComponent(b.name)}/restore`),
    onSuccess: (r, b) => {
      qc.invalidateQueries() // every screen now shows the restored data
      toast({ message: `Restored the backup from ${formatDateTime(b.created_at)}. Your previous data is saved as ${r.saved_current_as}.`, duration: 9000 })
    },
  })
  const ask = (b: BackupRow) =>
    confirm(`Restore the backup from ${formatDateTime(b.created_at)}?\n\n` +
      'Your current data is saved as a backup first, then replaced by this copy. Every job is rescored afterwards.') && restore.mutate(b)
  const rows = q.data ?? []
  if (rows.length === 0) return <ErrorText error={q.error} />
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium">Backups</h3>
      <ul className="divide-y rounded-lg border">
        {(all ? rows : rows.slice(0, SHOWN)).map((b) => (
          <li key={b.name} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-sm">
            <span className="min-w-0 flex-1 basis-52">
              <span className="font-medium">{formatDateTime(b.created_at)}</span>
              <span className="text-muted-foreground"> · {b.kind} · {size(b.size)}</span>
            </span>
            <Button size="sm" variant="outline" disabled={restore.isPending} onClick={() => ask(b)}
              aria-label={`Restore the backup from ${formatDateTime(b.created_at)}`}>
              {restore.isPending && restore.variables?.name === b.name ? 'Restoring…' : 'Restore…'}
            </Button>
          </li>
        ))}
      </ul>
      {rows.length > SHOWN && (
        <Button variant="ghost" size="sm" className="self-start" onClick={() => setAll(!all)}>
          {all ? 'Show fewer' : `Show all ${rows.length} backups`}
        </Button>
      )}
      <ErrorText error={restore.error} />
    </div>
  )
}
