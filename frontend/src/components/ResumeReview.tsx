import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { BaseResume, ExperienceItemInput, ItemType, ResumeDraft } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { ErrorText, ListInput, NativeSelect } from './common'

type Row = ExperienceItemInput & { _id: number; duplicate_of?: string | null; _skip?: boolean }

const SECTIONS: { key: string; title: string; types: ItemType[]; addType: ItemType; hint: string }[] = [
  { key: 'education', title: 'Education', types: ['education'], addType: 'education', hint: 'Degree or diploma, institution, dates.' },
  { key: 'work', title: 'Experience', types: ['work'], addType: 'work', hint: 'Jobs and internships. Each bullet becomes evidence for scoring.' },
  { key: 'project', title: 'Projects', types: ['project'], addType: 'project', hint: 'Personal, academic or freelance projects.' },
  { key: 'other', title: 'Achievements, certifications & publications', types: ['achievement', 'certification', 'publication'], addType: 'achievement', hint: 'Awards, activities, certificates, language tests, papers.' },
]
const TYPE_OPTIONS = [
  { value: 'education', label: 'Education' },
  { value: 'work', label: 'Experience' },
  { value: 'project', label: 'Project' },
  { value: 'certification', label: 'Certification' },
  { value: 'achievement', label: 'Achievement' },
  { value: 'publication', label: 'Publication' },
]
const EDU_LEVELS = ['', 'SPM', 'STPM', 'Diploma', 'Degree', 'Master', 'PhD']

/** What still needs a human look on one item. */
export function itemIssues(it: ExperienceItemInput): string[] {
  const out: string[] = []
  if (!it.title.trim()) out.push('title is empty')
  if ((it.type === 'work' || it.type === 'education') && !it.start.trim() && !it.end.trim()) out.push('dates are empty')
  if ((it.type === 'work' || it.type === 'project') && it.bullets.filter((b) => b.trim()).length === 0) out.push('no bullets')
  if (it.type === 'work' && !it.organization.trim()) out.push('organization is empty')
  return out
}

const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

function ItemCard({ row, onChange, onRemove, onFocus }: {
  row: Row
  onChange: (r: Row) => void
  onRemove: () => void
  onFocus: () => void
}) {
  const issues = itemIssues(row)
  const set = <K extends keyof Row>(k: K, v: Row[K]) => onChange({ ...row, [k]: v })
  const setBullet = (i: number, v: string) => set('bullets', row.bullets.map((b, j) => (j === i ? v : b)))
  return (
    <article
      id={`item-${row._id}`}
      onFocusCapture={onFocus}
      onMouseEnter={onFocus}
      className={cn('rounded-lg border bg-card', issues.length ? 'border-l-4 border-l-attention-edge' : '')}
    >
      <header className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-2 border-b p-4">
        <Input aria-label="Title" className="h-9 text-base font-semibold" placeholder="Title, e.g. Software Engineering Intern" value={row.title} onChange={(e) => set('title', e.target.value)} />
        <div className="flex items-center gap-1">
          <NativeSelect className="h-9" value={row.type} onChange={(v) => set('type', v as ItemType)} options={TYPE_OPTIONS} />
          <Button variant="ghost" size="icon" aria-label="Remove this item" onClick={onRemove}>
            <Trash2 />
          </Button>
        </div>
        <div className="col-span-2 grid grid-cols-[1fr_9rem_9rem] gap-2">
          <Input aria-label="Organization" placeholder="Organization" value={row.organization} onChange={(e) => set('organization', e.target.value)} />
          <Input aria-label="Start date" placeholder="e.g. Jun 2025" value={row.start} onChange={(e) => set('start', e.target.value)}
            className={cn(!row.start && !row.end && (row.type === 'work' || row.type === 'education') && 'border-attention-edge bg-attention-bg/40')} />
          <Input aria-label="End date" placeholder="e.g. Present" value={row.end} onChange={(e) => set('end', e.target.value)}
            className={cn(!row.start && !row.end && (row.type === 'work' || row.type === 'education') && 'border-attention-edge bg-attention-bg/40')} />
        </div>
      </header>
      <div className="flex flex-col gap-2 p-4">
        {row.bullets.map((b, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
            <textarea
              aria-label={`Bullet ${i + 1}`}
              rows={Math.max(1, Math.ceil(b.length / 90))}
              className="min-h-9 flex-1 resize-none rounded-md border border-transparent px-2 py-1.5 text-[15px] hover:border-input focus:border-ring focus:outline-none"
              value={b}
              onChange={(e) => setBullet(i, e.target.value)}
            />
            <Button variant="ghost" size="icon-sm" aria-label={`Remove bullet ${i + 1}`} onClick={() => set('bullets', row.bullets.filter((_, j) => j !== i))}>
              <Trash2 />
            </Button>
          </div>
        ))}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Button variant="ghost" size="sm" onClick={() => set('bullets', [...row.bullets, ''])}>
            <Plus /> Add bullet
          </Button>
          <label className="flex min-w-72 flex-1 items-center gap-2 text-sm text-muted-foreground">
            Skills
            <ListInput value={row.skills} onChange={(v) => set('skills', v)} placeholder="Detected automatically; add more, comma-separated" />
          </label>
        </div>
        {issues.length > 0 && (
          <p className="flex items-center gap-1.5 text-sm text-attention">
            <AlertTriangle className="size-4" /> Check this: {issues.join(', ')}.
          </p>
        )}
      </div>
    </article>
  )
}

function SourcePanel({ text, unparsed, highlight }: { text: string; unparsed: Set<string>; highlight: string[] }) {
  const lines = text.split('\n')
  const hl = highlight.map(squash).filter((h) => h.length > 3)
  return (
    <aside className="sticky top-4 flex max-h-[calc(100vh-2rem)] flex-col rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h3 className="font-semibold">Your resume as extracted</h3>
        <p className="text-sm text-muted-foreground">
          <span className="rounded bg-attention-bg px-1 text-attention">Highlighted lines</span> were not imported anywhere. Hover a card to see its source lines.
        </p>
      </div>
      <ol className="overflow-y-auto px-2 py-2 text-[14px] leading-relaxed">
        {lines.map((l, i) => {
          const key = squash(l.replace(/^\s*[-*•▪●◦]\s*/, ''))
          const isUnparsed = key && unparsed.has(key)
          const isHl = key && hl.some((h) => key.includes(h) || h.includes(key))
          return (
            <li
              key={i}
              className={cn(
                'rounded px-2 py-0.5 whitespace-pre-wrap',
                isUnparsed && 'bg-attention-bg text-attention',
                isHl && !isUnparsed && 'bg-selected',
                !l.trim() && 'h-3',
              )}
            >
              {l}
            </li>
          )
        })}
      </ol>
    </aside>
  )
}

/** Review the parsed draft. Nothing is saved until "Save to Experience Bank". */
export default function ResumeReview({ draft, onSaved, onCancel }: {
  draft: ResumeDraft
  onSaved: (msg: string) => void
  onCancel?: () => void
}) {
  const qc = useQueryClient()
  const [name, setName] = useState(draft.suggested_name)
  const [rows, setRows] = useState<Row[]>(() => draft.items.map((it, i) => ({ ...it, _id: i, _skip: !!it.duplicate_of })))
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => api.get<BaseResume[]>('/api/resumes') })
  const nameTaken = (resumes.data ?? []).some((r) => r.name.trim().toLowerCase() === name.trim().toLowerCase())
  const skipped = rows.filter((r) => r._skip).length
  const [nextId, setNextId] = useState(draft.items.length)
  const [prof, setProf] = useState(draft.profile)
  const [focusId, setFocusId] = useState<number | null>(null)

  const unparsedSet = useMemo(() => new Set(draft.unparsed_lines.map((u) => squash(u.line))), [draft.unparsed_lines])
  const issues = rows.filter((r) => !r._skip).flatMap((r) => itemIssues(r).map((m) => ({ id: r._id, label: `${r.title || 'Untitled item'}: ${m}` })))
  const profileGaps = (['name', 'email', 'education_level'] as const).filter((k) => !prof[k])
  const focused = rows.find((r) => r._id === focusId)

  const setRow = (r: Row) => setRows(rows.map((x) => (x._id === r._id ? r : x)))
  const addRow = (type: ItemType) => {
    setRows([...rows, { _id: nextId, type, title: '', organization: '', start: '', end: '', bullets: [''], skills: [] }])
    setNextId(nextId + 1)
  }
  const setP = <K extends keyof typeof prof>(k: K, v: (typeof prof)[K]) => setProf({ ...prof, [k]: v })

  const save = useMutation({
    mutationFn: () => {
      const profile: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(prof)) {
        if (Array.isArray(v) ? v.length : v) profile[k] = k === 'expected_graduation' && !v ? null : v
      }
      if (prof.degree_status !== 'in_progress') delete profile.expected_graduation
      // Degree status always has a value; only apply it when the resume actually gave an education level.
      if (!prof.education_level) delete profile.degree_status
      const items = rows.filter((r) => !r._skip)
        .map(({ _id, _skip, duplicate_of, ...it }) => ({ ...it, bullets: it.bullets.map((b) => b.trim()).filter(Boolean) }))
      return api.post<{ resume_id: number; item_codes: string[] }>('/api/resumes/import', {
        name, file_path: draft.file_path, raw_text: draft.raw_text, profile, items,
      })
    },
    onSuccess: (r) => {
      for (const k of ['experience', 'resumes', 'profile', 'jobs', 'job', 'dashboard']) qc.invalidateQueries({ queryKey: [k] })
      onSaved(`Saved ${r.item_codes.length} items to your Experience Bank (${r.item_codes.join(', ') || 'none'}).`)
    },
  })

  const field = (label: string, el: React.ReactNode, missing = false) => (
    <label className="flex flex-col gap-1">
      <span className={cn('text-sm font-medium', missing ? 'text-attention' : 'text-muted-foreground')}>{label}{missing && ' (missing)'}</span>
      {el}
    </label>
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold">Check what we read from your resume</h2>
          <p className="text-sm text-muted-foreground">
            Fix anything wrong, then save. Only what you keep here goes into your Experience Bank.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          Save as
          <Input aria-label="BaseResume name" className="w-48" value={name} onChange={(e) => setName(e.target.value)}
            aria-invalid={nameTaken} title={nameTaken ? 'This name is already used' : undefined} />
        </label>
        {onCancel && <Button variant="ghost" onClick={onCancel}>Discard</Button>}
        <Button onClick={() => save.mutate()} disabled={save.isPending || nameTaken || !name.trim()}>
          {save.isPending ? 'Saving…' : 'Save to Experience Bank'}
        </Button>
      </div>
      {nameTaken && <p className="text-sm text-attention">You already have a BaseResume called “{name.trim()}”. Choose another name to save.</p>}
      {(draft.skipped_sections ?? []).includes('references') && (
        <p className="text-sm text-muted-foreground">The References section was left out. Referee names and contact details are never imported.</p>
      )}
      <ErrorText error={save.error} />

      {(issues.length > 0 || draft.unparsed_lines.length > 0 || profileGaps.length > 0) ? (
        <div className="rounded-lg border border-attention-edge bg-attention-bg px-4 py-3 text-[15px] text-attention">
          <p className="font-semibold">
            {(() => {
              const n = issues.length + profileGaps.length + draft.unparsed_lines.length
              return n === 0 ? 'Nothing needs your attention' : n === 1 ? '1 thing needs your attention' : `${n} things need your attention`
            })()}
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {profileGaps.map((k) => <li key={k}><a className="underline" href="#review-profile">Profile: {k.replace('_', ' ')} missing</a></li>)}
            {issues.map((i, n) => <li key={n}><a className="underline" href={`#item-${i.id}`}>{i.label}</a></li>)}
            {draft.unparsed_lines.length > 0 && <li>{draft.unparsed_lines.length === 1 ? "1 line was" : `${draft.unparsed_lines.length} lines were`} not imported (highlighted on the right)</li>}
            {skipped > 0 && <li>{skipped} items are already in your bank and will be skipped</li>}
          </ul>
        </div>
      ) : (
        <div className="rounded-lg border bg-background px-4 py-3 text-[15px]">Everything was placed. Give it a quick read, then save.</div>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <section id="review-profile" className="flex flex-col gap-3">
            <div>
              <h3 className="text-lg font-semibold">Profile</h3>
              <p className="text-sm text-muted-foreground">Filled fields update your profile. Empty fields leave it unchanged.</p>
            </div>
            <div className="grid gap-3 rounded-lg border bg-card p-4 sm:grid-cols-2">
              {field('Name', <Input value={prof.name ?? ''} onChange={(e) => setP('name', e.target.value)} />, !prof.name)}
              {field('Email', <Input value={prof.email ?? ''} onChange={(e) => setP('email', e.target.value)} />, !prof.email)}
              {field('Phone', <Input value={prof.phone ?? ''} onChange={(e) => setP('phone', e.target.value)} />)}
              {field('Location', <Input value={prof.location ?? ''} onChange={(e) => setP('location', e.target.value)} />)}
              {field('Education level', <NativeSelect className="h-9" value={prof.education_level ?? ''} onChange={(v) => setP('education_level', v)} options={EDU_LEVELS.map((l) => ({ value: l, label: l || 'Not set' }))} />, !prof.education_level)}
              {field('Field of study', <Input value={prof.education_field ?? ''} onChange={(e) => setP('education_field', e.target.value)} />)}
              {field('Degree status', <NativeSelect className="h-9" value={prof.degree_status ?? 'completed'} onChange={(v) => setP('degree_status', v as 'completed' | 'in_progress')} options={[{ value: 'completed', label: 'Completed' }, { value: 'in_progress', label: 'In progress' }]} />)}
              {prof.degree_status === 'in_progress' && field('Expected graduation', <Input type="date" value={prof.expected_graduation ?? ''} onChange={(e) => setP('expected_graduation', e.target.value)} />, !prof.expected_graduation)}
            </div>
          </section>

          {SECTIONS.map((sec) => {
            const items = rows.filter((r) => sec.types.includes(r.type))
            if (sec.key === 'other' && items.length === 0) return null
            return (
              <section key={sec.key} className="flex flex-col gap-3">
                <div className="flex items-end justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-semibold">{sec.title} <span className="font-normal text-muted-foreground">({items.length})</span></h3>
                    <p className="text-sm text-muted-foreground">{sec.hint}</p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => addRow(sec.addType)}><Plus /> Add</Button>
                </div>
                {items.length === 0 && <p className="rounded-lg border border-dashed px-4 py-3 text-sm text-muted-foreground">Nothing found here. Add one if your resume has it.</p>}
                {items.map((r) => (
                  r._skip ? (
                    <div key={r._id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed bg-muted/50 px-4 py-2.5 text-[15px]">
                      <span><span className="font-medium">{r.title || 'Untitled'}</span>{r.organization && <span className="text-muted-foreground"> · {r.organization}</span>}
                        <span className="block text-sm text-muted-foreground">Already in your bank as {r.duplicate_of}. Skipped.</span></span>
                      <Button variant="outline" size="sm" onClick={() => setRow({ ...r, _skip: false })}>Import anyway</Button>
                    </div>
                  ) : (
                    <ItemCard key={r._id} row={r} onChange={setRow} onRemove={() => setRows(rows.filter((x) => x._id !== r._id))} onFocus={() => setFocusId(r._id)} />
                  )
                ))}
              </section>
            )
          })}

          <section className="flex flex-col gap-3">
            <div>
              <h3 className="text-lg font-semibold">Skills and languages</h3>
              <p className="text-sm text-muted-foreground">Skills you claim. They count as evidence labelled “profile” and are added to what you already have.</p>
            </div>
            <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
              {field('Skills', <ListInput value={prof.skills ?? []} onChange={(v) => setP('skills', v)} />)}
              <div className="flex flex-wrap gap-1.5">
                {(prof.skills ?? []).map((s) => <span key={s} className="rounded-sm bg-secondary px-2 py-0.5 text-sm">{s}</span>)}
              </div>
              {field('Languages', <ListInput value={prof.languages ?? []} onChange={(v) => setP('languages', v)} />)}
            </div>
          </section>
        </div>

        <SourcePanel
          text={draft.raw_text}
          unparsed={unparsedSet}
          highlight={focused ? [focused.title, focused.organization, ...focused.bullets] : []}
        />
      </div>
    </div>
  )
}
