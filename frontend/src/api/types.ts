export const STATUSES = ['Saved', 'Applied', 'Interview', 'Offer', 'Rejected', 'Withdrawn'] as const
export type Status = (typeof STATUSES)[number]

export type ItemStatus = 'met' | 'partial' | 'not_met' | 'not_specified'

export interface Profile {
  name: string
  email: string
  phone: string
  linkedin_url: string
  github_url: string
  portfolio_url: string
  location: string
  years_of_experience: number
  years_confirmed: boolean
  education_level: string
  education_field: string
  degree_status: 'completed' | 'in_progress'
  expected_graduation: string | null
  languages: string[]
  preferred_locations: string[]
  remote_ok: boolean
  skills: string[]
  notes: string
}

export type ItemType = 'work' | 'project' | 'education' | 'achievement' | 'certification' | 'publication'

export interface ExperienceItemInput {
  type: ItemType
  title: string
  organization: string
  start: string
  end: string
  bullets: string[]
  skills: string[]
  resume_ids?: number[]
}

export interface ExperienceItem extends ExperienceItemInput {
  id: number
  code: string
  resume_ids: number[]
}

export interface Skill {
  id: number
  name: string
  category: string
  aliases: string[]
}

export interface BaseResume {
  id: number
  name: string
  original_file_path: string
  created_at: string
  /** Last rename or change of its selection (created_at if never changed). */
  updated_at: string
  item_ids: number[]
}

export interface ResumeDraft {
  file_path: string
  raw_text: string
  suggested_name: string
  profile: Partial<Profile> & { expected_graduation: string }
  items: (ExperienceItemInput & { duplicate_of?: string | null })[]
  unparsed_lines: { line: string; section: string; reason: string }[]
  skipped_sections?: string[]
}

export interface JobSummary {
  id: number
  title: string
  company: string
  location: string
  salary_min: number | null
  salary_max: number | null
  salary_currency: string
  job_type: string
  work_arrangement: string
  posted_date: string | null
  urls: string[]
  sources: string[]
  fetched_at: string
  hidden: boolean
  hidden_reason: string
  hidden_by: string
  score: number | null
  gate_flags: string[]
  /** Saved from a search card only: the score is rough until the full JD is pasted. */
  summary_only: boolean
  /** Why the score can't be trusted (e.g. no recognised skills in the JD), or "". */
  low_confidence: string
  application_id: number | null
  application_status: Status | null
}

export interface BreakdownItem {
  name: string
  status: ItemStatus
  detail: string
  evidence: string[]
  group?: string[]
}

export interface BreakdownCategory {
  key: string
  label: string
  points: number
  max: number
  status: ItemStatus
  not_specified: boolean
  note: string
  items: BreakdownItem[]
}

export interface Breakdown {
  total: number
  raw_total: number
  capped: boolean
  gates: { key: string; message: string }[]
  categories: BreakdownCategory[]
  required_skills: string[]
  preferred_skills: string[]
  soft_skills?: { name: string; kind: string; status: ItemStatus; detail: string; evidence: string[] }[]
}

export interface Application {
  id: number
  job_id: number
  status: Status
  applied_at: string | null
  follow_up_at: string | null
  notes: string
  resume_version_id: number | null
  cover_letter_version_id: number | null
  created_at: string
  updated_at: string
}

export interface ApplicationRow extends Application {
  job_title: string
  company: string
  location: string
  score: number | null
}

export interface StatusHistory {
  id: number
  application_id: number
  from_status: Status | null
  to_status: Status
  changed_at: string
}

export interface JobDetail {
  job: Omit<JobSummary, 'summary_only' | 'low_confidence'> & { description: string; dedupe_key: string }
  summary_only: boolean
  low_confidence: string
  match: { total: number; breakdown: Breakdown; gate_flags: string[]; scored_at: string } | null
  application: Application | null
  history: StatusHistory[]
}

export interface FilterRule {
  id: number
  type: 'title_contains' | 'title_must_contain_one_of' | 'company_equals' | 'min_years_over' | 'min_salary_below' | 'keyword_in_jd'
  value: string
  action: string
  enabled: boolean
}

export interface ScoringConfig {
  weights: {
    required_skills: number
    preferred_skills: number
    years: number
    education: number
    language_location: number
  }
  gates: { years_short_by: number; cap: number; language: boolean; education: boolean }
  score_soft_skills: boolean
}

export interface Settings {
  scoring: ScoringConfig
  general: { follow_up_days: number; high_match_threshold: number; resume_projects_first: boolean }
  locations: Record<string, string[]>
}

export interface Dashboard {
  status_counts: Record<Status, number>
  applications_per_week: { week_start: string; count: number }[]
  response_rate: number | null
  high_match_jobs: { id: number; title: string; company: string; score: number }[]
  high_match_threshold: number
  unread_notifications: number
  follow_ups_due: number
  total_jobs: number
  sources: { key: string; label: string; status: string; note: string; paused_until: string | null; last_run_at: string | null }[]
  /** Today next-step keys snoozed until a date (ISO); only active ones. */
  snoozed: Record<string, string>
  /** Saved (not applied) jobs that already have a resume version: ready to send. */
  ready_to_apply: { job_id: number; title: string; company: string; document_id: number; version: number }[]
  /** Saved (not applied) jobs with no resume version yet. */
  saved_without_resume: { job_id: number; title: string; company: string }[]
}

export interface PasteDraft {
  title: string
  company: string
  location: string
  work_arrangement: string
  url: string
  uncertain: string[]
  source: string
  salary_undisclosed: boolean
  salary_min: number | null
  salary_max: number | null
  salary_currency: string
  job_type: string
  description: string
  detected: string[]
  removed_lines: number
}

export interface JobDraft {
  title: string
  company: string
  location: string
  work_arrangement: string
  description: string
  url: string
  salary_min: number | null
  salary_max: number | null
  salary_currency: string
  job_type: string
}

export interface ProfileStatus {
  education: { level: string; field: string; in_progress: boolean; expected: string; source: string } | null
  missing: { key: string; label: string; fix: string; hint: string }[]
}

export interface SourceRow {
  key: string
  label: string
  enabled: boolean
  status: 'ok' | 'error' | 'paused'
  paused_until: string | null
  last_run_at: string | null
  last_error: string
  last_result: string
  runs_today: number
  max_results: number
  max_runs_per_day: number
  hard_max_results: number
  hard_max_runs_per_day: number
  can_run: boolean
  /** A fetch for this source is in progress right now. */
  running: boolean
  fake_mode: boolean
}

export interface SearchProfileRow {
  id: number
  name: string
  keywords: string[]
  locations: string[]
  job_type: string
  days: number
  sources: string[]
  max_results: number
  enabled: boolean
}

export interface AutomationRunRow {
  id: number
  automation_key: string
  trigger: string
  started_at: string
  finished_at: string | null
  result: 'running' | 'ok' | 'error' | 'skipped'
  items_processed: number
  message: string
  error: string
  /** fetch_jobs only (newer runs): one entry per source. */
  details?: RunSourceDetail[]
}

export interface RunSourceDetail {
  source: string
  status: 'ok' | 'error' | 'paused' | 'skipped'
  profiles: string[]
  cap: number | null
  fetched: number
  new: number
  merged: number
  hidden: number
  requests: number
  notes: string[]
  error: string
}

export interface AutomationRow {
  key: string
  label: string
  description: string
  enabled: boolean
  mode: 'scheduled' | 'manual'
  schedule: string
  daily: boolean
  default_enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  last_run: AutomationRunRow | null
}

export interface NotificationRow {
  id: number
  type: string
  message: string
  link: string
  read: boolean
  created_at: string
}

export interface SkillGapRow {
  skill: string
  required: number
  preferred: number
  total: number
  jobs: { id: number; title: string; company: string; score: number; kind: string }[]
}

// ---------- Phase 3: AI and documents ----------

export type AiMode = 'copy_paste' | 'ollama' | 'off'
export type AiTaskType = 'parse_resume' | 'deep_analysis' | 'tailor_resume' | 'cover_letter' | 'interview_prep'

export interface AiSettings {
  mode: AiMode
  ollama_model: string
  ollama_timeout_s: number
  auto_analysis_max_per_run: number
}

export interface OllamaStatus {
  running: boolean
  models: string[]
  model: string
  installed: boolean
  message: string
}

export interface PromptTemplate {
  name: string
  text: string
  edited: boolean
  placeholders: string[]
}

export interface FieldError { path: string; message: string }
export interface GuardFlag { path: string; kind: 'unknown_id' | 'missing_id' | 'unknown_skill' | 'not_in_source' | 'new_number' | 'skill_not_in_item' | 'header_removed' | 'several_bullets' | 'placeholder'; message: string }

export interface AiTask<R = Record<string, unknown>> {
  id: number
  task: AiTaskType
  job_id: number | null
  provider: 'copy_paste' | 'ollama'
  status: 'waiting' | 'running' | 'parsed' | 'invalid' | 'failed' | 'saved'
  prompt: string
  response: string
  errors: FieldError[]
  flags: GuardFlag[]
  repairs: string[]
  result: R | null
  error_message: string
  document_id: number | null
  created_at: string
  updated_at: string
}

export interface TailorResult {
  summary: string
  skills_order: string[]
  sections: { section: string; items: { source_id: string; text: string }[] }[]
  omitted_ids: string[]
  notes: string
}

export interface CoverLetterResult {
  greeting: string
  paragraphs: string[]
  closing: string
  used_ids: string[]
}

export interface DeepAnalysisResult {
  requirements: { text: string; type: 'required' | 'preferred'; status: 'met' | 'partial' | 'not_met'; evidence_ids: string[]; note: string }[]
  overall_fit: number
  strengths: string[]
  gaps: string[]
  resume_suggestions: string[]
  flags?: GuardFlag[]
}

export interface InterviewPrepResult {
  questions: { question: string; category: string; why_likely: string; suggested_points_ids: string[] }[]
  flags?: GuardFlag[]
}

export interface ParseResumeResult {
  profile: { name: string; email: string; phone: string; location: string; education_level: string; education_field: string; languages: string[]; skills: string[] }
  items: ExperienceItemInput[]
}

export type DocumentType = 'resume' | 'cover_letter' | 'interview_prep' | 'deep_analysis'

export interface DocumentRow {
  id: number
  job_id: number | null
  type: DocumentType
  version: number
  content: Record<string, unknown>
  pdf_path: string
  source: 'copy_paste' | 'ollama' | 'template' | 'manual'
  ai_task_id: number | null
  created_at: string
  has_pdf: boolean
  printable: boolean
}

export interface TemplateDraft extends CoverLetterResult {
  skills: string[]
  suggested_ids: string[]
}
