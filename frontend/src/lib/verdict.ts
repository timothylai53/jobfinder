/** Plain-English summaries of a job's state: the one-sentence score verdict and the next action. */
import type { Breakdown, BreakdownItem } from '@/api/types'

export type VerdictTone = 'strong' | 'partial' | 'weak' | 'blocked' | 'rough'

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1)

/** What a ⚠️ / ❌ item outside the skill lists means, in a few words. */
function concern(categoryKey: string, item: BreakdownItem): string | null {
  if (item.status !== 'partial' && item.status !== 'not_met') return null
  if (categoryKey === 'years') return `asks for ${item.name.replace(/ required$/, '')}`
  if (categoryKey === 'education') {
    if (item.name.startsWith('Field:')) return 'different field of study'
    if (item.status === 'partial' && /in progress/i.test(item.detail)) return 'degree still in progress'
    return `needs ${item.name.replace(/ or higher$/, '')}`
  }
  if (categoryKey === 'language_location') {
    if (item.name.startsWith('Location:')) return 'outside your preferred locations'
    return `needs ${item.name.replace(/ \((required|preferred)\)$/, '')}`
  }
  return null
}

/** "Strong match: all 4 required skills; degree still in progress." */
export function scoreVerdict(b: Breakdown, opts: { summaryOnly?: boolean; lowConfidence?: string } = {}): { tone: VerdictTone; text: string } {
  if (opts.summaryOnly) return { tone: 'rough', text: 'Rough estimate from the search summary only. Paste the full job ad for a real score.' }
  if (b.gates.length > 0) return { tone: 'blocked', text: `Blocked by a hard requirement: ${lower(b.gates[0].message)}.` }
  if (opts.lowConfidence) return { tone: 'rough', text: `Low confidence: ${lower(opts.lowConfidence)}.` }

  const tone: VerdictTone = b.total >= 70 ? 'strong' : b.total >= 50 ? 'partial' : 'weak'
  const head = { strong: 'Strong match', partial: 'Partial match', weak: 'Weak match' }[tone]
  const req = b.categories.find((c) => c.key === 'required_skills')
  let skills = 'no required skills listed'
  if (req && !req.not_specified && req.items.length > 0) {
    const n = req.items.length
    const met = req.items.filter((i) => i.status === 'met').length
    skills = met === n ? `all ${n} required skill${n === 1 ? '' : 's'}` : `${met} of ${n} required skills`
  }
  const concerns: string[] = []
  for (const c of b.categories) {
    for (const i of c.items) {
      const text = concern(c.key, i)
      if (text && !concerns.includes(text)) concerns.push(text)
    }
  }
  return { tone, text: `${head}: ${[skills, ...concerns.slice(0, 2)].join('; ')}.` }
}

/** Everything marked ⚠️ or ❌, with its category, for the Overview tab. */
export function gaps(b: Breakdown): { category: string; item: BreakdownItem }[] {
  return b.categories.flatMap((c) =>
    c.items.filter((i) => i.status === 'partial' || i.status === 'not_met').map((item) => ({ category: c.label, item })))
}

export type PrimaryStep = 'save' | 'tailor' | 'download' | 'mark_applied' | 'done'

/** The one next action for a job: Save to tracker → Tailor resume → Download resume → Mark as applied. */
export function primaryStep(s: { tracked: boolean; status?: string; hasResume: boolean; downloaded: boolean }): PrimaryStep {
  if (!s.tracked) return 'save'
  if (s.status && s.status !== 'Saved') return 'done'
  if (!s.hasResume) return 'tailor'
  return s.downloaded ? 'mark_applied' : 'download'
}
