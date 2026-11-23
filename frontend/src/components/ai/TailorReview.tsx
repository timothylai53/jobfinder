import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, Scissors, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { AiTask, BaseResume, DocumentRow, ExperienceItem, GuardFlag, TailorResult } from '@/api/types'
import { ErrorText, FlagIcon } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { acceptedSections, blocksSave, flagsAt, flagTone, isWarning, sentences, splitRow, tailorRows, type TailorRow, unusedCodes } from '@/lib/ai'
import { splitLeftOut } from '@/lib/baseResumes'
import { dateRange } from '@/lib/score'
import { cn } from '@/lib/utils'

function FlagList({ flags }: { flags: GuardFlag[] }) {
  if (!flags.length) return null
  return <ul className="text-sm">{flags.map((f, i) => <li key={i} className={isWarning(f) ? 'text-attention' : 'text-danger'}><FlagIcon />{f.message}</li>)}</ul>
}

/**
 * Side-by-side review (brief §6.6 point 4): the original bank item on the left, the rewritten text on the right.
 * Accept, edit or reject each item. Only accepted content is saved, as a new resume version.
 */
export default function TailorReview({ task, onSaved }: { task: AiTask<TailorResult>; onSaved: (d: DocumentRow) => void }) {
  const result = task.result!
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const byCode = useMemo(() => new Map((bank.data ?? []).map((b) => [b.code.toUpperCase(), b])), [bank.data])
  const [rows, setRows] = useState<TailorRow[]>(() => tailorRows(result, task.flags))
  const [summary, setSummary] = useState(result.summary)
  const [skills, setSkills] = useState<string[]>(() => result.skills_order.filter((_, i) => !flagsAt(task.flags, `skills_order.${i}`).length))
  const [extra, setExtra] = useState<string[]>([])
  const flaggedSkills = result.skills_order.filter((_, i) => flagsAt(task.flags, `skills_order.${i}`).length)
  const unused = unusedCodes((bank.data ?? []).map((b) => b.code), rows)
  // Tailored from a base resume: its own unused items first, then the rest of the bank (which the AI never saw).
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => api.get<BaseResume[]>('/api/resumes'), enabled: !!task.base_resume_id })
  const base = resumes.data?.find((r) => r.id === task.base_resume_id)
  const baseCodes = base ? new Set((bank.data ?? []).filter((b) => base.item_ids.includes(b.id)).map((b) => b.code.toUpperCase())) : null
  const leftOut = splitLeftOut(unused, baseCodes)
  const update = (key: string, patch: Partial<TailorRow>) => setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  const summaryFlags = flagsAt(task.flags, 'summary')

  const save = useMutation({
    mutationFn: () => api.post<DocumentRow>('/api/documents/resume', {
      job_id: task.job_id, source: task.provider, ai_task_id: task.id, summary, skills,
      sections: acceptedSections(rows), add_original_ids: extra,
    }),
    onSuccess: onSaved,
  })
  const accepted = rows.filter((r) => r.decision === 'accepted').length

  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-1">
        <h3 className="font-medium">Summary</h3>
        <Textarea rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} className={cn(summaryFlags.length && 'border-danger-edge')} />
        <FlagList flags={summaryFlags} />
      </section>

      <section className="flex flex-col gap-1">
        <h3 className="font-medium">Skills, most relevant first</h3>
        <div className="flex flex-wrap gap-1.5">
          {skills.map((s) => (
            <span key={s} className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-sm">
              {s}
              <button aria-label={`Remove ${s}`} onClick={() => setSkills(skills.filter((x) => x !== s))}><X className="size-3" /></button>
            </span>
          ))}
          {flaggedSkills.filter((s) => !skills.includes(s)).map((s) => (
            <button key={s} title="Not in your bank or profile. Click to add it anyway." onClick={() => setSkills([...skills, s])}
              className="rounded-md border border-danger-edge bg-danger-bg px-2 py-0.5 text-sm text-danger line-through">{s}</button>
          ))}
        </div>
        {flaggedSkills.length > 0 && <p className="text-sm text-danger">Crossed out: not in your bank or profile, left out.</p>}
      </section>

      <section className="flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-3 text-sm font-medium text-muted-foreground">
          <span>Original (Experience Bank)</span><span>Rewritten for this job</span>
        </div>
        {rows.map((r, i) => {
          const b = byCode.get(r.source_id.trim().toUpperCase())
          const header = i === 0 || rows[i - 1].section !== r.section
          const unsavable = r.flags.some(blocksSave) && !b
          return (
            <div key={r.key}>
              {header && <h3 className="mt-2 mb-1 border-b pb-1 font-semibold">{r.section}</h3>}
              <div className={cn('grid grid-cols-2 gap-3 rounded-lg border p-2', flagTone(r.flags) === 'red' && 'border-danger-edge bg-danger-bg/40', flagTone(r.flags) === 'amber' && 'border-attention-edge bg-attention-bg/40', r.decision === 'rejected' && 'opacity-60')}>
                <div className="text-sm">
                  {b ? (
                    <>
                      <div><span className="font-medium">{b.title}</span>{b.organization && <span className="text-muted-foreground"> · {b.organization}</span>}{(b.start || b.end) && <span className="text-muted-foreground"> · {dateRange(b.start, b.end)}</span>}<span className="ml-1.5 text-xs text-muted-foreground">{b.code}</span></div>
                      <ul className="mt-1 list-disc pl-4 text-muted-foreground">{b.bullets.map((x, i) => <li key={i}>{x}</li>)}</ul>
                    </>
                  ) : (
                    <div className="font-medium text-danger">No bank item “{r.source_id || 'none'}”: nothing to compare with.</div>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <Textarea rows={2} value={r.text} onChange={(e) => update(r.key, { text: e.target.value })} disabled={r.decision === 'rejected'} className="text-sm" />
                  <FlagList flags={r.flags} />
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-xs text-muted-foreground">
                      ID <Input className="h-7 w-16 text-xs" value={r.source_id} onChange={(e) => update(r.key, { source_id: e.target.value })} />
                    </label>
                    {r.text !== r.original && <span className="text-xs text-muted-foreground">edited</span>}
                    {r.decision === 'accepted' && sentences(r.text).length > 1 && (
                      <Button size="sm" variant="outline" title="One bullet per sentence, same bank item" onClick={() => setRows((rs) => splitRow(rs, r.key))}>
                        <Scissors className="size-4" /> Split into {sentences(r.text).length} bullets
                      </Button>
                    )}
                    <div className="ml-auto flex gap-1">
                      <Button size="sm" variant={r.decision === 'accepted' ? 'selected' : 'outline'} aria-pressed={r.decision === 'accepted'} disabled={unsavable}
                        title={unsavable ? 'Give it the ID of a real bank item first' : undefined}
                        onClick={() => update(r.key, { decision: 'accepted' })}><Check className="size-4" /> Accept</Button>
                      <Button size="sm" variant={r.decision === 'rejected' ? 'selected' : 'outline'} aria-pressed={r.decision === 'rejected'} onClick={() => update(r.key, { decision: 'rejected' })}><X className="size-4" /> Reject</Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </section>

      {unused.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className="font-medium">Bank items the AI left out</h3>
          <p className="text-sm text-muted-foreground">Tick any you want on this resume as written in your bank (education and certifications are often worth keeping).</p>
          {base && leftOut.inBase.length > 0 && <h4 className="text-sm font-medium">From {base.name}</h4>}
          <LeftOutList codes={leftOut.inBase} byCode={byCode} extra={extra} setExtra={setExtra} />
          {leftOut.others.length > 0 && (
            <>
              <h4 className="mt-1 text-sm font-medium">Other bank items <span className="font-normal text-muted-foreground">(not in {base?.name ?? 'this base resume'}, so the AI didn't see them)</span></h4>
              <LeftOutList codes={leftOut.others} byCode={byCode} extra={extra} setExtra={setExtra} />
            </>
          )}
        </section>
      )}

      {result.notes && <div className="rounded-lg bg-muted px-3 py-2 text-sm"><span className="font-medium">AI notes (gaps and suggestions, not on the resume): </span>{result.notes}</div>}

      <div className="flex items-center justify-end gap-2">
        <ErrorText error={save.error} />
        <span className="text-sm text-muted-foreground">{accepted} of {rows.length} items accepted</span>
        <Button disabled={save.isPending || (accepted === 0 && extra.length === 0)} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : 'Save as new resume version'}
        </Button>
      </div>
    </div>
  )
}

function LeftOutList({ codes, byCode, extra, setExtra }: {
  codes: string[]; byCode: Map<string, ExperienceItem>; extra: string[]; setExtra: (x: string[]) => void
}) {
  return (
    <ul className="flex flex-col gap-1">
      {codes.map((c) => {
        const b = byCode.get(c.toUpperCase())
        return (
          <li key={c}>
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-0.5 size-4 accent-foreground" checked={extra.includes(c)}
                onChange={(e) => setExtra(e.target.checked ? [...extra, c] : extra.filter((x) => x !== c))} />
              <span>
                <span className="font-medium">{b?.title}</span>
                {b?.organization && <span className="text-muted-foreground"> · {b.organization}</span>}
                {b && (b.start || b.end) && <span className="text-muted-foreground"> · {dateRange(b.start, b.end)}</span>}
                <span className="ml-1.5 text-xs text-muted-foreground">{c}</span>
              </span>
            </label>
          </li>
        )
      })}
    </ul>
  )
}
