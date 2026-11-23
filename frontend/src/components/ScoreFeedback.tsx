import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import { ErrorText } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useLocalCopy } from '@/lib/hooks'
import { RATING_LABEL, type Rating, type ScoreRating } from '@/lib/scoreCheck'

const ORDER: Rating[] = ['too_high', 'about_right', 'too_low']

/** "Does this score feel right?" One click on Job Detail, changeable later; feeds Settings → Score check. */
export default function ScoreFeedback({ jobId }: { jobId: number }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['rating', jobId], queryFn: () => api.get<ScoreRating | null>(`/api/jobs/${jobId}/rating`) })
  const [note, setNote] = useLocalCopy(q.data?.note ?? '')
  const done = (r: ScoreRating | null) => {
    qc.setQueryData(['rating', jobId], r)
    qc.invalidateQueries({ queryKey: ['score-check'] })
  }
  const rate = useMutation({
    mutationFn: (body: { rating: Rating; note: string }) => api.put<ScoreRating>(`/api/jobs/${jobId}/rating`, body),
    onSuccess: done,
  })
  const clear = useMutation({ mutationFn: () => api.del(`/api/jobs/${jobId}/rating`), onSuccess: () => done(null) })
  const current = q.data?.rating
  if (q.isLoading) return null
  return (
    <div className="mt-3 flex flex-col gap-2 text-sm" role="group" aria-labelledby={`feel-${jobId}`}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span id={`feel-${jobId}`} className="mr-1 text-muted-foreground">Does this score feel right?</span>
        {ORDER.map((r) => (
          <Button key={r} size="sm" variant={current === r ? 'selected' : 'outline'} aria-pressed={current === r}
            disabled={rate.isPending} onClick={() => rate.mutate({ rating: r, note })}>
            {RATING_LABEL[r]}
          </Button>
        ))}
        {current && (
          <Button size="sm" variant="ghost" className="text-muted-foreground" disabled={clear.isPending} onClick={() => clear.mutate()}>
            Clear
          </Button>
        )}
      </div>
      {current && current !== 'about_right' && (
        <Input aria-label="Why? (optional)" placeholder="Why? e.g. it really needs Docker…" maxLength={300} value={note}
          className="max-w-md" onChange={(e) => setNote(e.target.value)}
          onBlur={() => note !== (q.data?.note ?? '') && rate.mutate({ rating: current, note })} />
      )}
      <ErrorText error={q.error || rate.error || clear.error} />
    </div>
  )
}
