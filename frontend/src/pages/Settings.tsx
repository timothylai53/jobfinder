import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { api } from '@/api/client'
import type { Profile, ScoringConfig, Settings as SettingsT } from '@/api/types'
import { ErrorText, Field, ListInput, NativeSelect, PageHeader } from '@/components/common'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Link, useSearchParams } from 'react-router-dom'
import { educationLabel, useProfileStatus } from '@/lib/profile'
import PreferredLocations from '@/components/PreferredLocations'
import { JobSources, SearchProfiles } from '@/components/SourceSettings'
import { AiSettingsTab, PromptTemplatesTab } from '@/components/ai/AiSettings'
import { cn } from '@/lib/utils'
import { Textarea } from '@/components/ui/textarea'
import FilterRules from '@/components/FilterRules'
import LocationMapEditor from '@/components/LocationMapEditor'
import { useToast } from '@/lib/toast'
import { readLocal, writeLocal } from '@/lib/storage'
import SkillDictionary from '@/components/SkillDictionary'
import { formatDateTime } from '@/lib/score'
import { useLocalCopy } from '@/lib/hooks'
import { confirmLeave, useUnsavedChanges } from '@/lib/unsaved'
import ScoreCheck from '@/components/ScoreCheck'

const EDU_LEVELS = ['', 'SPM', 'STPM', 'Diploma', 'Degree', 'Master', 'PhD']

function useRescoreInvalidate() {
  const qc = useQueryClient()
  return () => {
    for (const k of ['profile', 'settings', 'filters', 'skills', 'jobs', 'job', 'dashboard', 'applications']) qc.invalidateQueries({ queryKey: [k] })
  }
}

// ---------- profile ----------

export function ProfileTab({ onSaved, saveLabel = 'Save profile' }: { onSaved?: () => void; saveLabel?: string }) {
  const q = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const [p, setP] = useLocalCopy<Profile | null>(q.data ?? null)
  const done = useRescoreInvalidate()
  // Saving this form confirms the years of experience, even when it stays 0.
  const qc = useQueryClient()
  // The reply becomes the saved copy at once, so the form is clean before any navigation that follows.
  const save = useMutation({
    mutationFn: (v: Profile) => api.put<Profile>('/api/profile', { ...v, years_confirmed: true }),
    onSuccess: (saved) => { qc.setQueryData(['profile'], saved); done(); onSaved?.() },
  })
  useUnsavedChanges(!!p && !!q.data && JSON.stringify(p) !== JSON.stringify(q.data))
  const status = useProfileStatus()
  if (!p) return <ErrorText error={q.error} />
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v })
  return (
    <Card>
      <CardContent>
        <form
          className="grid gap-4 sm:grid-cols-2"
          onSubmit={(e) => {
            e.preventDefault()
            save.mutate(p)
          }}
        >
          <Field label="Name"><Input name="name" autoComplete="name" value={p.name} onChange={(e) => set('name', e.target.value)} /></Field>
          <Field label="Email"><Input type="email" name="email" autoComplete="email" spellCheck={false} value={p.email} onChange={(e) => set('email', e.target.value)} /></Field>
          <Field label="Phone"><Input type="tel" name="tel" autoComplete="tel" value={p.phone} onChange={(e) => set('phone', e.target.value)} /></Field>
          <Field label="LinkedIn URL"><Input name="linkedin" inputMode="url" autoComplete="url" spellCheck={false} value={p.linkedin_url} placeholder="e.g. linkedin.com/in/your-name" onChange={(e) => set('linkedin_url', e.target.value)} /></Field>
          <Field label="GitHub URL"><Input name="github" inputMode="url" autoComplete="off" spellCheck={false} value={p.github_url} placeholder="e.g. github.com/your-name" onChange={(e) => set('github_url', e.target.value)} /></Field>
          <Field label="Portfolio URL"><Input name="portfolio" inputMode="url" autoComplete="off" spellCheck={false} value={p.portfolio_url} placeholder="Optional" onChange={(e) => set('portfolio_url', e.target.value)} />
            <span className="text-sm text-muted-foreground">Links are printed in your resume and cover-letter header. They're never put in AI prompts.</span>
          </Field>
          <Field label="Where you live"><Input name="city" autoComplete="address-level2" value={p.location} placeholder="e.g. Petaling Jaya" onChange={(e) => set('location', e.target.value)} /></Field>
          <Field label="Years of work experience">
            <Input type="number" step="0.5" min="0" value={p.years_of_experience} onChange={(e) => set('years_of_experience', Number(e.target.value))} />
            <span className="text-sm text-muted-foreground">Internships can count. Leave at 0 if you are a fresh graduate.</span>
          </Field>
          <div className="rounded-md bg-muted px-3 py-2 text-sm sm:col-span-2">
            <span className="font-medium">Education used for matching: </span>
            {educationLabel(status.data?.education ?? null)}
            <span className="block text-muted-foreground">
              The highest of your Experience Bank education items and the fields below counts. A degree in progress earns half the education points and never blocks a job.
            </span>
          </div>
          <Field label="Highest education">
            <NativeSelect className="h-9" value={p.education_level} onChange={(v) => set('education_level', v)} options={EDU_LEVELS.map((l) => ({ value: l, label: l || 'Not set' }))} />
          </Field>
          <Field label="Field of study"><Input value={p.education_field} placeholder="e.g. Software Engineering" onChange={(e) => set('education_field', e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Degree status">
              <NativeSelect
                className="h-9"
                value={p.degree_status}
                onChange={(v) => set('degree_status', v as Profile['degree_status'])}
                options={[{ value: 'completed', label: 'Completed' }, { value: 'in_progress', label: 'In progress' }]}
              />
            </Field>
            {p.degree_status === 'in_progress' && (
              <Field label="Expected graduation">
                <Input type="date" value={p.expected_graduation ?? ''} onChange={(e) => set('expected_graduation', e.target.value || null)} />
              </Field>
            )}
          </div>
          <Field label="Languages you speak" className="sm:col-span-2">
            <ListInput value={p.languages} onChange={(v) => set('languages', v)} placeholder="e.g. English, Bahasa Malaysia, Mandarin (comma-separated)" />
          </Field>
          <Field label="Skills you claim" className="sm:col-span-2">
            <ListInput value={p.skills} onChange={(v) => set('skills', v)} placeholder="e.g. Python, React, SQL (comma-separated)" />
            <span className="text-sm text-muted-foreground">These count as evidence labelled “profile”. Skills from Experience Bank items are added automatically.</span>
          </Field>
          <Field label="Notes" className="sm:col-span-2"><Textarea rows={2} value={p.notes} onChange={(e) => set('notes', e.target.value)} /></Field>
          <div className="flex items-center justify-end gap-2 sm:col-span-2">
            {save.isSuccess && <span className="text-sm text-muted-foreground">Saved. Jobs rescored.</span>}
            <ErrorText error={save.error} />
            <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : saveLabel}</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ---------- filters ----------

function FiltersTab() {
  return <FilterRules onChanged={useRescoreInvalidate()} />
}

// ---------- scoring + general ----------

const WEIGHT_LABELS: [keyof ScoringConfig['weights'], string][] = [
  ['required_skills', 'Required skills'],
  ['preferred_skills', 'Preferred skills'],
  ['years', 'Years of experience'],
  ['education', 'Education'],
  ['language_location', 'Language + location'],
]

function ScoringTab() {
  const q = useQuery({ queryKey: ['settings'], queryFn: () => api.get<SettingsT>('/api/settings') })
  const [s, setS] = useLocalCopy<SettingsT | null>(q.data ?? null)
  const done = useRescoreInvalidate()
  // Locations are edited in their own tab; omitting them leaves the stored map unchanged.
  const toast = useToast()
  const qc = useQueryClient()
  useUnsavedChanges(!!s && !!q.data && JSON.stringify(s) !== JSON.stringify(q.data))
  const save = useMutation({
    mutationFn: (v: SettingsT) => api.put<SettingsT>('/api/settings', { scoring: v.scoring, general: v.general }),
    onSuccess: (saved) => { qc.setQueryData(['settings'], saved); done(); toast({ message: 'Scoring saved. Jobs rescored.' }) },
  })
  const defaults = useQuery({ queryKey: ['scoring-defaults'], queryFn: () => api.get<ScoringConfig>('/api/settings/scoring/defaults') })
  const sum = useMemo(() => (s ? Object.values(s.scoring.weights).reduce((a, b) => a + b, 0) : 0), [s])
  if (!s) return <ErrorText error={q.error} />
  const w = (k: keyof ScoringConfig['weights'], v: number) => setS({ ...s, scoring: { ...s.scoring, weights: { ...s.scoring.weights, [k]: v } } })
  const g = <K extends keyof ScoringConfig['gates']>(k: K, v: ScoringConfig['gates'][K]) =>
    setS({ ...s, scoring: { ...s.scoring, gates: { ...s.scoring.gates, [k]: v } } })
  const num = (v: string) => (v === '' ? 0 : Number(v))
  return (
    <Card>
      <CardContent className="flex flex-col gap-6">
        <section aria-labelledby="weights" className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="weights" className="font-semibold">How the 100 points are split</h3>
            <p className={cn('text-sm tabular-nums', sum === 100 ? 'text-muted-foreground' : 'text-attention')} aria-live="polite">
              Total {sum}{sum !== 100 && ': it is scaled to 100 when scoring'}
            </p>
          </div>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(9rem,1fr))] gap-3">
            {WEIGHT_LABELS.map(([k, label]) => (
              <Field key={k} label={label}>
                <Input type="number" min="0" value={s.scoring.weights[k]} onChange={(e) => w(k, num(e.target.value))} />
              </Field>
            ))}
          </div>
        </section>

        <section aria-labelledby="gates" className="flex flex-col gap-3 border-t pt-5">
          <div>
            <h3 id="gates" className="font-semibold">Hard requirements</h3>
            <p className="text-sm text-muted-foreground">A job that misses one of these gets its score capped, so it never looks like a good fit.</p>
          </div>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(16rem,1fr))] gap-3">
            <Field label="Years short that count as a miss">
              <Input type="number" min="0" step="0.5" value={s.scoring.gates.years_short_by} onChange={(e) => g('years_short_by', num(e.target.value))} />
            </Field>
            <Field label="Highest score after a miss">
              <Input type="number" min="0" max="100" value={s.scoring.gates.cap} onChange={(e) => g('cap', num(e.target.value))} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-[15px]">
            <input type="checkbox" className="size-4 accent-foreground" checked={s.scoring.gates.language} onChange={(e) => g('language', e.target.checked)} />
            A required language you don't speak is a miss
          </label>
          <label className="flex items-center gap-2 text-[15px]">
            <input type="checkbox" className="size-4 accent-foreground" checked={s.scoring.gates.education} onChange={(e) => g('education', e.target.checked)} />
            A required degree you don't have (and aren't studying for) is a miss
          </label>
        </section>

        <section aria-labelledby="soft" className="border-t pt-5">
          <h3 id="soft" className="sr-only">Soft skills</h3>
          <label className="flex items-start gap-2 text-[15px]">
            <input type="checkbox" className="mt-1 size-4 accent-foreground" checked={s.scoring.score_soft_skills}
              onChange={(e) => setS({ ...s, scoring: { ...s.scoring, score_soft_skills: e.target.checked } })} />
            <span>
              <span className="font-medium">Score soft skills</span>
              <span className="block text-sm text-muted-foreground">
                Off: Communication, Problem Solving, Teamwork and other soft skills are listed under each job but earn no points.
                On: they count toward the required and preferred skill points like any other skill.
              </span>
            </span>
          </label>
        </section>

        <section aria-labelledby="alerts" className="flex flex-col gap-3 border-t pt-5">
          <h3 id="alerts" className="font-semibold">Reminders and alerts</h3>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(16rem,1fr))] gap-3">
            <Field label="Suggest a follow-up after (days)">
              <Input type="number" min="1" max="90" value={s.general.follow_up_days} onChange={(e) => setS({ ...s, general: { ...s.general, follow_up_days: num(e.target.value) } })} />
            </Field>
            <Field label="Tell me about new jobs scoring at least">
              <Input type="number" min="0" max="100" value={s.general.high_match_threshold} onChange={(e) => setS({ ...s, general: { ...s.general, high_match_threshold: num(e.target.value) } })} />
            </Field>
          </div>
        </section>

        <div className="flex items-center justify-end gap-2 border-t pt-4">
          <ErrorText error={save.error} />
          <Button variant="ghost" onClick={() => defaults.data && setS({ ...s, scoring: defaults.data })}>Reset scoring to defaults</Button>
          <Button onClick={() => save.mutate(s)} disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save and rescore'}</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ---------- skills and locations ----------

function SkillsTab() {
  return <SkillDictionary onChanged={useRescoreInvalidate()} />
}

function LocationsTab() {
  return <LocationMapEditor onSaved={useRescoreInvalidate()} />
}

// ---------- export / backup ----------

interface BackupStatus {
  last_backup_at: string | null
  last_backup_name: string | null
  last_backup_automatic: boolean
  automatic_kept: number
  keep_automatic: number
}

function ExportTab() {
  const status = useQuery({ queryKey: ['backup-status'], queryFn: () => api.get<BackupStatus>('/api/backup/status') })
  const qc = useQueryClient()
  const backup = useMutation({
    mutationFn: () => api.post<{ path: string; name: string }>('/api/backup'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backup-status'] }),
  })
  const b = status.data
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          <Button asChild><a href="/api/export/xlsx">Download Excel (.xlsx)</a></Button>
          <Button asChild variant="outline"><a href="/api/export/jobs.csv">Jobs CSV</a></Button>
          <Button asChild variant="outline"><a href="/api/export/applications.csv">Applications CSV</a></Button>
        </div>
        <div className="flex flex-col gap-2 border-t pt-3">
          <p className="text-[15px]">
            <span className="font-medium">Last backup: </span>
            {b?.last_backup_at
              ? <>{formatDateTime(b.last_backup_at)} <span className="text-muted-foreground">({b.last_backup_automatic ? 'automatic' : 'manual'})</span></>
              : <span className="text-muted-foreground">none yet</span>}
          </p>
          <p className="text-sm text-muted-foreground">
            A backup is made automatically once a day when JobFinder starts; the last {b?.keep_automatic ?? 14} are kept
            ({b?.automatic_kept ?? 0} now). Backups you make yourself are never deleted.
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => backup.mutate()} disabled={backup.isPending}>Backup database now</Button>
            {backup.data && <span className="text-sm text-muted-foreground">Saved {backup.data.name}</span>}
            <ErrorText error={backup.error || status.error} />
          </div>
        </div>
        <p className="text-sm text-muted-foreground">Backups are copies of data/jobfinder.db in data/backups/. To restore one, run stop.bat and copy it back over data/jobfinder.db.</p>
      </CardContent>
    </Card>
  )
}

function ResumeLayoutTab() {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['settings'], queryFn: () => api.get<SettingsT>('/api/settings') })
  const save = useMutation({
    mutationFn: (on: boolean) => api.put('/api/settings', { scoring: q.data!.scoring, general: { ...q.data!.general, resume_projects_first: on } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
  if (!q.data) return <ErrorText error={q.error} />
  return (
    <Card>
      <CardContent className="flex flex-col gap-2">
        <label className="flex items-start gap-2 text-[15px]">
          <input type="checkbox" className="mt-1" checked={q.data.general.resume_projects_first} disabled={save.isPending}
            onChange={(e) => save.mutate(e.target.checked)} />
          <span>
            <span className="font-medium">Projects before Experience</span>
            <span className="block text-sm text-muted-foreground">
              Order of these two sections in resume PDFs and previews. Applies to every version the next time you download or preview it.
            </span>
          </span>
        </label>
        <ErrorText error={save.error} />
      </CardContent>
    </Card>
  )
}

const SECTIONS = [
  { group: 'Basic', id: 'profile', title: 'Profile', desc: 'Your experience, education and languages. The quick score compares every job against this.', el: <ProfileTab /> },
  { group: 'Basic', id: 'locations', title: 'Preferred locations', desc: 'Where you want to work. Pick whole states, specific towns, or Remote.', el: <div className="rounded-lg border bg-card p-4"><PreferredLocations /></div> },
  { group: 'Basic', id: 'search-profiles', title: 'Search profiles', desc: 'What to search for: keywords, locations, job type and how recent. Used by Fetch now and the daily fetch.', el: <SearchProfiles /> },
  { group: 'Basic', id: 'sources', title: 'Job sources', desc: 'Which sites to fetch from, their health, and how much each may fetch per run and per day.', el: <JobSources /> },
  { group: 'Basic', id: 'filters', title: 'Filter rules', desc: 'Hide jobs you never want to see, such as senior roles or certain companies.', el: <FiltersTab /> },
  { group: 'Basic', id: 'resume-layout', title: 'Resume layout', desc: 'How resume PDFs are laid out.', el: <ResumeLayoutTab /> },
  { group: 'Basic', id: 'ai', title: 'AI', desc: 'Copy-Paste (default), Ollama on this laptop, or off. No paid AI service is ever used.', el: <AiSettingsTab /> },
  { group: 'Advanced', id: 'scoring', title: 'Scoring weights & gates', desc: 'How the 0–100 quick score is split between categories, and when it is capped.', el: <ScoringTab /> },
  { group: 'Advanced', id: 'skills', title: 'Skill dictionary', desc: 'The skills and aliases the matcher recognises in job descriptions and your resume.', el: <SkillsTab /> },
  { group: 'Advanced', id: 'location-map', title: 'Location map', desc: 'Which towns and areas belong to each state. Used by Preferred locations.', el: <LocationsTab /> },
  { group: 'Advanced', id: 'prompts', title: 'Prompt templates', desc: 'The instructions sent with each AI task. The rules, your bank and the output format are always added.', el: <PromptTemplatesTab /> },
  { group: 'Advanced', id: 'score-check', title: 'Score check', desc: 'How often the quick score matches your own judgement, from the jobs you rated.', el: <ScoreCheck /> },
  { group: 'Advanced', id: 'export', title: 'Export & backup', desc: 'Download your jobs and applications, or copy the database to a backup file.', el: <ExportTab /> },
] as const

export default function Settings() {
  const [params] = useSearchParams()
  const [id, setId] = useState<string>(() => {
    const saved = params.get('section') ?? readLocal('settingsSection')
    return SECTIONS.some((s) => s.id === saved) ? saved! : 'profile'
  })
  // Follow ?section= links (from the "profile is missing …" banner) even when already on this page.
  const linked = params.get('section')
  const [seenLinked, setSeenLinked] = useState(linked)
  if (linked !== seenLinked) {
    setSeenLinked(linked)
    if (linked && SECTIONS.some((s) => s.id === linked)) setId(linked)
  }
  const current = SECTIONS.find((s) => s.id === id) ?? SECTIONS[0]
  const pick = (v: string) => {
    if (v !== id && !confirmLeave()) return
    setId(v)
    writeLocal('settingsSection', v)
  }
  return (
    <div>
      <PageHeader title="Settings" lead="Your profile, what to search for, and how scoring and AI work.">
        <Button variant="outline" asChild><Link to="/setup">Run setup again</Link></Button>
      </PageHeader>
      <div className="grid items-start gap-6 md:grid-cols-[15rem_minmax(0,1fr)]">
        <nav aria-label="Settings sections" className="flex flex-col gap-5 md:sticky md:top-6">
          {(['Basic', 'Advanced'] as const).map((g) => (
            <div key={g}>
              <h2 className="mb-1 px-3 text-sm font-semibold text-muted-foreground">{g}</h2>
              <ul className="flex flex-col">
                {SECTIONS.filter((s) => s.group === g).map((s) => (
                  <li key={s.id}>
                    <button
                      onClick={() => pick(s.id)}
                      aria-current={s.id === id ? 'page' : undefined}
                      className={cn(
                        'w-full rounded-md px-3 py-1.5 text-left text-[15px] hover:bg-muted',
                        s.id === id && 'bg-selected font-medium text-foreground',
                      )}
                    >
                      {s.title}
                    </button>
                  </li>
                ))}
              </ul>
              {g === 'Advanced' && <p className="mt-1 px-3 text-xs text-muted-foreground">Defaults work well. Change these only if a score looks wrong.</p>}
            </div>
          ))}
        </nav>
        <section aria-labelledby="settings-title" className="flex min-w-0 flex-col gap-3">
          <div>
            <h2 id="settings-title" className="text-xl font-semibold">{current.title}</h2>
            <p className="text-[15px] text-muted-foreground">{current.desc}</p>
          </div>
          {current.el}
        </section>
      </div>
    </div>
  )
}
