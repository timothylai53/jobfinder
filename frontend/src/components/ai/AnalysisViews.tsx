import type { DeepAnalysisResult, GuardFlag, InterviewPrepResult } from '@/api/types'
import { flagsAt } from '@/lib/ai'
import { StatusMark, FlagIcon } from '@/components/common'
import { cn } from '@/lib/utils'

function Ids({ ids, flags, path }: { ids: string[]; flags: GuardFlag[]; path: string }) {
  if (!ids.length) return null
  return (
    <span className="text-[13px]">
      {ids.map((id, i) => {
        const bad = flagsAt(flags, `${path}.${i}`).length > 0
        return <span key={i} title={bad ? 'Not in your Experience Bank' : undefined} className={cn('mr-1 rounded px-1', bad ? 'bg-red-100 text-red-700 line-through' : 'bg-muted')}>{id}</span>
      })}
    </span>
  )
}

function List({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null
  return (
    <div>
      <h4 className="font-medium">{title}</h4>
      <ul className="list-disc pl-5 text-sm">{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
    </div>
  )
}

/** Deep analysis: each requirement met / partly met / not met, with the bank items that prove it (unknown IDs crossed out in red). */
export function DeepAnalysisView({ data, flags = [] }: { data: DeepAnalysisResult; flags?: GuardFlag[] }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="text-[15px]"><span className="font-semibold">Overall fit: {data.overall_fit}/100</span> <span className="text-sm text-muted-foreground">(the AI's estimate; the quick score is separate)</span></div>
      <ul className="flex flex-col gap-1.5">
        {data.requirements.map((r, i) => {
          const f = flagsAt(flags, `requirements.${i}`).filter((x) => x.path === `requirements.${i}`)
          return (
            <li key={i} className={cn('rounded-md border px-2 py-1.5 text-sm', f.length && 'border-red-300 bg-red-50/40')}>
              <StatusMark status={r.status} className="mr-1.5 inline-block align-[-3px]" />
              <span className="font-medium">{r.text}</span>
              <span className="ml-1 text-[13px] text-muted-foreground">({r.type})</span>{' '}
              <Ids ids={r.evidence_ids} flags={flags} path={`requirements.${i}.evidence_ids`} />
              {r.note && <div className="text-muted-foreground">{r.note}</div>}
              {f.map((x, k) => <div key={k} className="text-red-700"><FlagIcon />{x.message}</div>)}
            </li>
          )
        })}
      </ul>
      <List title="Strengths" items={data.strengths} />
      <List title="Gaps" items={data.gaps} />
      <List title="Resume suggestions" items={data.resume_suggestions} />
    </div>
  )
}

export function InterviewPrepView({ data, flags = [] }: { data: InterviewPrepResult; flags?: GuardFlag[] }) {
  return (
    <ol className="flex list-decimal flex-col gap-2 pl-5">
      {data.questions.map((q, i) => (
        <li key={i} className="text-[15px]">
          <span className="font-medium">{q.question}</span>
          {q.category && <span className="ml-1 rounded bg-muted px-1 text-xs">{q.category}</span>}
          {q.why_likely && <div className="text-sm text-muted-foreground">{q.why_likely}</div>}
          {q.suggested_points_ids.length > 0 && (
            <div className="text-sm">Draw on: <Ids ids={q.suggested_points_ids} flags={flags} path={`questions.${i}.suggested_points_ids`} /></div>
          )}
        </li>
      ))}
    </ol>
  )
}
