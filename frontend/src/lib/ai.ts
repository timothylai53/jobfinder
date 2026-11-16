/** Pure helpers for the AI review screens (tested in ai.test.ts). */
import type { ExperienceItem, ExperienceItemInput, GuardFlag, ParseResumeResult, ResumeDraft, TailorResult } from '@/api/types'

/** Flags for one field: its own path, or anything under it ("sections.0.items.2" also gets "...items.2.text"). */
export function flagsAt(flags: GuardFlag[], path: string): GuardFlag[] {
  return flags.filter((f) => f.path === path || f.path.startsWith(path + '.'))
}

/** A flag that makes an item unsavable: its bank ID is missing or unknown. */
export const blocksSave = (f: GuardFlag) => f.kind === 'missing_id' || f.kind === 'unknown_id'

/** Amber, not red: a skill I have but not in this bullet's bank item, a repeated header that was removed,
 * or several bullets merged into one. */
const WARNINGS = new Set<GuardFlag['kind']>(['skill_not_in_item', 'header_removed', 'several_bullets'])
export const isWarning = (f: GuardFlag) => WARNINGS.has(f.kind)

const ABBREV = new Set(['e.g', 'i.e', 'etc', 'vs', 'sdn', 'bhd', 'inc', 'ltd', 'co', 'dr', 'mr', 'ms', 'no', 'approx'])

/** Split a merged paragraph into one bullet per sentence (same rule as the backend's guard.sentences). */
export function sentences(text: string): string[] {
  const out: string[] = []
  let start = 0
  for (const m of text.matchAll(/[.!?;]\s+(?=[A-Z])/g)) {
    const word = /([\w.]+)$/.exec(text.slice(start, m.index))
    if (m[0][0] === '.' && word && ABBREV.has(word[1].toLowerCase().replace(/\.+$/, ''))) continue
    out.push(text.slice(start, m.index + 1).trim().replace(/;$/, ''))
    start = m.index + m[0].length
  }
  out.push(text.slice(start).trim())
  return out.filter(Boolean)
}

/** Replace one review row with one row per sentence, same bank ID and section. Its other flags stay on every piece. */
export function splitRow(rows: TailorRow[], key: string): TailorRow[] {
  return rows.flatMap((r) => {
    if (r.key !== key) return [r]
    const parts = sentences(r.text)
    if (parts.length < 2) return [r]
    const flags = r.flags.filter((f) => f.kind !== 'several_bullets')
    return parts.map((text, n) => ({ ...r, key: `${key}.${n}`, text, original: text, flags }))
  })
}

/** Row/box colour for a set of flags: red if any is red, amber if all are warnings. */
export const flagTone = (flags: GuardFlag[]): 'red' | 'amber' | null =>
  !flags.length ? null : flags.every(isWarning) ? 'amber' : 'red'

export type Decision = 'accepted' | 'rejected'

export interface TailorRow {
  key: string // "s.i" path into the AI result
  section: string
  source_id: string
  text: string
  original: string // the AI's text, to show what was edited
  flags: GuardFlag[]
  decision: Decision
}

/** One row per rewritten item. Rows whose ID is missing or unknown start rejected (they can't be saved as is). */
export function tailorRows(result: TailorResult, flags: GuardFlag[]): TailorRow[] {
  return result.sections.flatMap((sec, s) =>
    sec.items.map((it, i) => {
      const f = flagsAt(flags, `sections.${s}.items.${i}`)
      return {
        key: `${s}.${i}`,
        section: sec.section,
        source_id: it.source_id,
        text: it.text,
        original: it.text,
        flags: f,
        decision: f.some(blocksSave) ? 'rejected' : 'accepted',
      }
    }),
  )
}

/** Accepted rows, grouped back into sections in their original order (the body for POST /api/documents/resume). */
export function acceptedSections(rows: TailorRow[]): { section: string; items: { source_id: string; text: string }[] }[] {
  const out: { section: string; items: { source_id: string; text: string }[] }[] = []
  for (const r of rows) {
    if (r.decision !== 'accepted' || !r.text.trim()) continue
    let sec = out.find((s) => s.section === r.section)
    if (!sec) out.push((sec = { section: r.section, items: [] }))
    sec.items.push({ source_id: r.source_id.trim(), text: r.text.trim() })
  }
  return out
}

/** Bank codes the AI didn't use at all (offered as "include as written"). */
export function unusedCodes(allCodes: string[], rows: TailorRow[]): string[] {
  const used = new Set(rows.map((r) => r.source_id.trim().toUpperCase()))
  return allCodes.filter((c) => !used.has(c.toUpperCase()))
}

const squash = (s: string) => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()
/** Same key as the backend's item_key(): type, title, organization and dates, ignoring case and punctuation. */
export const itemKey = (it: ExperienceItemInput) => [it.type, it.title, it.organization, it.start, it.end].map(squash).join('|')

/** An AI resume parse -> the same draft shape the review screen already uses (nothing is saved here).
 * Items already in the bank are marked as duplicates, so the review screen skips them by default. */
export function parsedToDraft(result: ParseResumeResult, base: ResumeDraft, bank: ExperienceItem[] = []): ResumeDraft {
  const existing = new Map(bank.map((b) => [itemKey(b), b.code]))
  const p = result.profile
  return {
    ...base,
    profile: {
      ...base.profile,
      name: p.name || base.profile.name,
      email: p.email || base.profile.email,
      phone: p.phone || base.profile.phone,
      location: p.location || base.profile.location,
      education_level: p.education_level || base.profile.education_level,
      education_field: p.education_field || base.profile.education_field,
      languages: p.languages.length ? p.languages : base.profile.languages,
      skills: p.skills.length ? p.skills : base.profile.skills,
    },
    items: result.items.map((it: ExperienceItemInput) => ({ ...it, duplicate_of: existing.get(itemKey(it)) ?? null })),
    unparsed_lines: [],
  }
}

export const TASK_LABEL: Record<string, string> = {
  parse_resume: 'Parse resume',
  deep_analysis: 'Deep analysis',
  tailor_resume: 'Tailor resume',
  cover_letter: 'Cover letter',
  interview_prep: 'Interview prep',
}
