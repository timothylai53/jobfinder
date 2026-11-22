/** The Skill dictionary table: search, category filter and sorting. */
import type { Skill } from '@/api/types'

export type SkillSort = 'name' | 'category'

export function visibleSkills(skills: Skill[], query: string, category: string, sort: SkillSort, desc: boolean): Skill[] {
  const q = query.trim().toLowerCase()
  const rows = skills.filter((s) =>
    (!category || s.category === category) &&
    (!q || s.name.toLowerCase().includes(q) || s.aliases.some((a) => a.toLowerCase().includes(q))))
  const by = (s: Skill) => (sort === 'name' ? s.name : `${s.category}\u0000${s.name}`).toLowerCase()
  rows.sort((a, b) => by(a).localeCompare(by(b)))
  return desc ? rows.reverse() : rows
}

/** Categories in use plus the usual ones, sorted, for the filter and the editor's dropdown. */
export function skillCategories(skills: Skill[]): string[] {
  const base = ['cloud', 'concept', 'data', 'database', 'design', 'devops', 'framework', 'it', 'language', 'mobile',
    'other', 'process', 'soft', 'testing', 'tools', 'web']
  return [...new Set([...base, ...skills.map((s) => s.category).filter(Boolean)])].sort()
}
