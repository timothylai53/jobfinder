/** Base resumes: how their bank items are grouped, counted and searched. */
import type { ExperienceItem, ItemType } from '@/api/types'

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
