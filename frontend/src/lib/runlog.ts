/** The Automations run log: one row per source of a fetch (or per run for other automations), in plain words. */
import type { AutomationRunRow, RunSourceDetail } from '@/api/types'

export type RowStatus = 'ok' | 'error' | 'paused' | 'skipped' | 'running'

export interface RunLogRow {
  key: string
  runId: number
  at: string
  /** What to filter by: a source key for fetch rows, the automation key otherwise. */
  group: string
  name: string
  status: RowStatus
  /** "Smoke test · limit 5" for a fetch, how it was started for the rest. */
  meta: string
  numbers: { fetched: number; new: number; merged: number; hidden: number; requests: number } | null
  /** Plain-language warnings and messages, shown under Details. */
  details: string[]
}

export const STATUS_LABEL: Record<RowStatus, string> = { ok: 'OK', error: 'Error', paused: 'Paused', skipped: 'Skipped', running: 'Running' }

export const SOURCE_LABEL: Record<string, string> = { jobstreet: 'JobStreet', linkedin: 'LinkedIn', indeed: 'Indeed', glassdoor: 'Glassdoor' }
const sourceName = (key: string) => SOURCE_LABEL[key] ?? key

const TRIGGER: Record<string, string> = { manual: 'Run by you', schedule: 'Scheduled', 'catch-up': 'Catch-up after start', chain: 'After Fetch jobs' }

const FILTER_WORDS: Record<string, string> = { job_type: 'job type', is_remote: 'remote', easy_apply: 'Easy Apply' }

/** Turn a source's raw warning into a sentence ("LinkedIn doesn't support the job type filter, so it was ignored."). */
export function plainNote(source: string, raw: string): string {
  const name = sourceName(source)
  const note = raw.replace(/^JobSpy warning:\s*/i, '').trim()
  let m = note.match(/^(?:job_type \w+|(\w+)) isn't supported, ignoring it$/)
  if (m) return `${name} doesn't support the ${FILTER_WORDS[m[1] ?? 'job_type'] ?? m[1]} filter, so it was ignored.`
  m = note.match(/^location '(.+)' not found, searching (the country|all countries)$/)
  if (m) return `${name} didn't recognise “${m[1]}”, so it searched ${m[2]} instead.`
  m = note.match(/^empty page at start=(\d+)/)
  if (m) return `${name} stopped returning results after ${m[1]} jobs (the end of the list, or it slowed us down).`
  if (/^skipping job:/.test(note)) return `${name} skipped a job it couldn't read.`
  m = note.match(/^(\d+) of (\d+) \w+ results came back without a description$/)
  if (m) return `${m[1]} of ${m[2]} ${name} results came back without a description.`
  m = note.match(/^job (?:pages|details) blocked: saved (\d+) job\(s\) from (?:the|their) search (?:results only|summary)$/)
  if (m) return `${name} blocked the job pages, so ${m[1]} job(s) were saved from the search results only.`
  const s = note.charAt(0).toUpperCase() + note.slice(1)
  return /[.!?)]$/.test(s) ? s : `${s}.`
}

export function metaText(profiles: string[], cap: number | null): string {
  return [profiles.join(', '), cap ? `limit ${cap}` : ''].filter(Boolean).join(' · ')
}

const SUMMARY = /(\d+) fetched, (\d+) new, (\d+) merged, (\d+) hidden by filters/
const LEGACY = /^(\w+)(?: \(limit (\d+), profiles? (.*?)\))?: (ok|skipped|error|paused): (.*) \((\d+) request\(s\)\)$/

/** Older runs only kept a text line per source: "indeed (limit 5, profile Smoke test): ok: 3 fetched, … (2 request(s))". */
export function parseLegacyLine(line: string): RunSourceDetail | null {
  const m = line.match(LEGACY)
  if (!m) return null
  const [, source, cap, profiles, status, text, requests] = m
  const n = text.match(SUMMARY)
  const before = n ? text.slice(0, n.index).replace(/\.?\s*Saved before stopping:\s*$/, '').trim() : text
  const after = n ? text.slice((n.index ?? 0) + n[0].length).replace(/^\.\s*/, '') : ''
  return {
    source, status: status as RunSourceDetail['status'], cap: cap ? Number(cap) : null,
    profiles: profiles && profiles !== 'none' ? profiles.split(', ') : [],
    fetched: Number(n?.[1] ?? 0), new: Number(n?.[2] ?? 0), merged: Number(n?.[3] ?? 0), hidden: Number(n?.[4] ?? 0),
    requests: Number(requests), notes: after ? after.split('; ') : [], error: status === 'ok' ? '' : before,
  }
}

export function runRows(run: AutomationRunRow, automationLabel: string): RunLogRow[] {
  const base = { runId: run.id, at: run.started_at }
  if (run.automation_key === 'fetch_jobs' && run.result !== 'running') {
    const details = run.details?.length ? run.details : run.message.split('\n').map(parseLegacyLine).filter((d): d is RunSourceDetail => !!d)
    if (details.length > 0) {
      return details.map((d) => ({
        ...base, key: `${run.id}-${d.source}`, group: d.source, name: sourceName(d.source), status: d.status,
        meta: metaText(d.profiles, d.cap),
        numbers: d.status === 'skipped' ? null : { fetched: d.fetched, new: d.new, merged: d.merged, hidden: d.hidden, requests: d.requests },
        details: [...(d.error ? [d.status === 'skipped' ? `Skipped: ${d.error}.` : plainNote(d.source, d.error)] : []),
          ...d.notes.map((n) => plainNote(d.source, n))],
      }))
    }
  }
  const lines = [run.error, ...run.message.split('\n')].map((l) => l.trim()).filter(Boolean)
  return [{
    ...base, key: String(run.id), group: run.automation_key, name: automationLabel, status: run.result,
    meta: [TRIGGER[run.trigger] ?? run.trigger, run.items_processed ? `${run.items_processed} processed` : ''].filter(Boolean).join(' · '),
    numbers: null,
    details: lines.map((l) => (/[.!?)]$/.test(l) ? l : `${l}.`)).map((l) => l.charAt(0).toUpperCase() + l.slice(1)),
  }]
}

/** One short line for an automation's last run: "3 sources, 7 new jobs", "1 follow-up due today", or the error. */
export function lastRunSummary(run: AutomationRunRow): string {
  if (run.result === 'running') return 'Running now'
  if (run.error) return run.error
  if (run.details?.length) {
    const ran = run.details.filter((d) => d.status !== 'skipped')
    const fresh = run.details.reduce((n, d) => n + d.new, 0)
    const failed = ran.filter((d) => d.status === 'error' || d.status === 'paused').length
    return [`${ran.length} ${ran.length === 1 ? 'source' : 'sources'}`, `${fresh} new ${fresh === 1 ? 'job' : 'jobs'}`,
      failed ? `${failed} with problems` : ''].filter(Boolean).join(', ')
  }
  const first = run.message.split('\n')[0].trim()
  return first ? first.charAt(0).toUpperCase() + first.slice(1) : 'Nothing to do'
}
