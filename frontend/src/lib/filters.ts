/** Filter rules in plain words (Settings → Filter rules). */
import type { FilterRule } from '@/api/types'

export const FILTER_TYPES: { value: FilterRule['type']; label: string; hint: string; numeric?: boolean }[] = [
  { value: 'title_contains', label: 'Title contains', hint: 'Comma-separated words, e.g. Senior, Lead, Manager' },
  { value: 'title_must_contain_one_of', label: 'Title has none of', hint: 'Comma-separated words: jobs whose title has none of them are hidden. 2-letter words (IT, QA) must be whole words; longer ones also match a longer word ("test" matches Tester)' },
  { value: 'company_equals', label: 'Company is', hint: 'Comma-separated company names (suffixes like Sdn Bhd are ignored)' },
  { value: 'min_years_over', label: 'Asks for more years than', hint: 'A number, e.g. 2: hides jobs requiring more than 2 years', numeric: true },
  { value: 'min_salary_below', label: 'Salary below', hint: 'A number in RM, e.g. 3000: jobs with no salary shown are never hidden', numeric: true },
  { value: 'keyword_in_jd', label: 'Job ad mentions', hint: 'Comma-separated words or phrases' },
]

/** "Hide jobs whose title contains Senior, Lead or Manager." */
export function ruleSentence(r: Pick<FilterRule, 'type' | 'value'>): string {
  const words = r.value.split(',').map((w) => w.trim()).filter(Boolean)
  const list = words.length > 1 ? `${words.slice(0, -1).join(', ')} or ${words[words.length - 1]}` : words[0] ?? '…'
  switch (r.type) {
    case 'title_contains': return `Hide jobs whose title contains ${list}.`
    case 'title_must_contain_one_of': return `Hide jobs whose title has none of ${list}.`
    case 'company_equals': return `Hide jobs from ${list}.`
    case 'min_years_over': return `Hide jobs asking for more than ${r.value.trim() || '…'} years.`
    case 'min_salary_below': return `Hide jobs paying under RM ${r.value.trim() || '…'} (jobs with no salary shown stay).`
    case 'keyword_in_jd': return `Hide jobs whose ad mentions ${list}.`
  }
}
