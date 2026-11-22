/** Base resumes: how their bank items are grouped, counted and searched. */
import type { BaseResume, ExperienceItem, ItemType } from '@/api/types'

/** Groups in resume order, with the words used in the one-line summary ("2 education · 3 projects"). */
export const GROUPS: { type: ItemType; label: string; one: string; many: string }[] = [
  { type: 'education', label: 'Education', one: 'education', many: 'education' },
  { type: 'work', label: 'Experience', one: 'work', many: 'work' },
  { type: 'project', label: 'Projects', one: 'project', many: 'projects' },
  { type: 'certification', label: 'Certifications', one: 'certification', many: 'certifications' },
  { type: 'publication', label: 'Publications', one: 'publication', many: 'publications' },
  { type: 'achievement', label: 'Achievements', one: 'achievement', many: 'achievements' },
]

/** "2 education · 3 projects · 2 work · 5 achievements", in resume order; "No items yet" when empty. */
export function typeSummary(items: Pick<ExperienceItem, 'type'>[]): string {
  const parts = GROUPS.map((g) => {
    const n = items.filter((i) => i.type === g.type).length
    return n ? `${n} ${n === 1 ? g.one : g.many}` : ''
  }).filter(Boolean)
  return parts.join(' · ') || 'No items yet'
}

/** Bank items grouped by type (empty groups left out), filtered by a search over title, organisation, code and skills. */
export function groupItems(items: ExperienceItem[], query: string) {
  const q = query.trim().toLowerCase()
  const hit = (i: ExperienceItem) =>
    !q || [i.title, i.organization, i.code, ...i.skills].some((s) => s.toLowerCase().includes(q))
  return GROUPS.map((g) => ({ ...g, items: items.filter((i) => i.type === g.type && hit(i)) })).filter((g) => g.items.length > 0)
}

/** Ticks or unticks every item of a group (only the ones shown, so a search narrows "select all"). */
export function toggleGroup(selected: Set<number>, ids: number[], on: boolean): Set<number> {
  const next = new Set(selected)
  for (const id of ids) {
    if (on) next.add(id)
    else next.delete(id)
  }
  return next
}

/** "Start from" default for tailoring: the most recently used base resume that still has items, else null (whole bank). */
export function defaultStartFrom(resumes: BaseResume[]): number | null {
  const used = resumes.filter((r) => r.last_used_at && r.item_ids.length > 0)
  used.sort((a, b) => Date.parse(b.last_used_at!) - Date.parse(a.last_used_at!))
  return used[0]?.id ?? null
}

/** The review's "left out" list, split: the base resume's own items first, then the rest of the bank. */
export function splitLeftOut(unused: string[], baseCodes: Set<string> | null): { inBase: string[]; others: string[] } {
  if (!baseCodes) return { inBase: unused, others: [] }
  return { inBase: unused.filter((c) => baseCodes.has(c.toUpperCase())), others: unused.filter((c) => !baseCodes.has(c.toUpperCase())) }
}
