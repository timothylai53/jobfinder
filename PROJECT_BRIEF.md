# Project Brief: Personal Job Finder (local web app)

You are building a personal, single-user job search system that runs entirely on my own Windows laptop. Read this whole brief before writing any code. Then propose an implementation plan for **Phase 1 only** and wait for my approval before you start coding. Build one phase at a time. Every phase must be usable on its own before the next one starts.

---

## 1. Context

- I am a Software Engineering student in Malaysia, looking for jobs (fresh grad level).
- I am the only user. The app runs on `localhost`. There are no user accounts and no login.
- My laptop runs Windows, has 20 GB RAM and a GTX 1050 with 3 GB VRAM. Design for that hardware.
- Run it in a local Claude Code Desktop session inside the project folder.

## 2. Core principles (in priority order)

1. **Accurate.** Scores and analysis must be explainable, and the AI must never invent experience or skills.
2. **Efficient.** It should be fast to use day to day, with few clicks.
3. **Simple.** No over-engineering. Choose the simplest design that works. Don't add features this brief does not ask for.
4. **100% free.** No paid APIs, no paid services, no paid scraping tools (no Apify, no proxies). Everything must work offline except for fetching job listings.
5. **Private.** All data stays on my laptop. Nothing is sent anywhere unless I explicitly copy it out myself.
6. **Account-safe.** The system must **never** log in to any job site with my credentials, and must never store job-site usernames or passwords. Scraping uses only public, logged-out endpoints, at conservative rates.

## 3. Tech stack (use exactly this unless you have a strong reason and ask me first)

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLModel (on SQLAlchemy), Pydantic v2 |
| Database | SQLite, a single file at `data/jobfinder.db` |
| Scheduler | APScheduler (in-process, started with the FastAPI app) |
| Scraping | `python-jobspy` for LinkedIn / Indeed / Glassdoor; a custom `httpx` module for JobStreet |
| Resume parsing | `pypdf` / `pdfplumber` for PDF, `python-docx` for DOCX |
| Local LLM (optional) | Ollama over its local HTTP API (`http://localhost:11434`), using small models (3B–4B by default, user-selectable) |
| PDF export | HTML/CSS resume template (Jinja2) rendered to PDF with Playwright (headless Chromium) |
| Frontend | React + Vite + TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, React Router |
| Tests | pytest (backend), Vitest for critical frontend logic only |

- No Docker. No Next.js. No embeddings or vector DB in v1.
- Provide `start.bat` that starts the backend and frontend and opens the browser, plus `setup.bat` for first-time installs (venv, pip, npm, Playwright Chromium).
- Commit to git at the end of each working milestone.

## 4. Architecture

```
frontend/ (React)  ──HTTP/JSON──>  backend/ (FastAPI)  ──>  SQLite (data/jobfinder.db)
                                        │
                                        ├── sources/        (jobstreet.py, jobspy_source.py, manual.py) — plugin interface
                                        ├── resume_parser/  (PDF/DOCX → structured profile draft)
                                        ├── experience_bank/
                                        ├── skills/         (skill dictionary + alias matching)
                                        ├── filters/
                                        ├── matcher/        (rule-based quick score)
                                        ├── ai/             (providers: copy_paste, ollama, off; prompt templates; tolerant parser; validators)
                                        ├── documents/      (resume / cover letter / interview prep versions, PDF export)
                                        ├── tracker/        (applications, status history, reminders)
                                        ├── scheduler/      (automations, run log, catch-up)
                                        ├── notifications/
                                        └── export/         (Excel/CSV)
```

**Main data flow:**
source fetch → normalize to one Job shape → dedupe → apply filter rules → save full JD snapshot → quick score → notify if score ≥ threshold → I review → (optional) deep analysis / tailor resume / cover letter, each saved as a new version → I apply → tracker status updates → follow-up reminders.

Every module has one clear job and a small interface, and can be tested on its own.

## 5. Data model (SQLite via SQLModel; adjust field details as needed, keep the concepts)

- **Profile**: name, contact, location, years_of_experience (number I set manually), education level + field, languages (e.g. English, BM, Mandarin), preferred locations, notes.
- **BaseResume**: name (e.g. "Software Dev", "IT Support"), original file path, parsed raw text, created_at.
- **ExperienceItem** (the Experience Bank): stable short ID (e.g. `B12`), type (work / project / education / achievement / certification), title, organization, start/end dates, bullet text, linked skills, which BaseResumes include it.
- **Skill**: canonical name, category, aliases (list). Seed with a sensible dictionary of common tech and soft skills, with aliases (e.g. `JavaScript` ← `JS`, `ECMAScript`; `React` ← `React.js`, `ReactJS`). I can add and edit skills in the UI.
- **SearchProfile**: keywords, locations, job type, date range, enabled sources, max results per source.
- **Source**: key, enabled, status (ok / error / paused), paused_until, last_run_at, last_error, daily_run_count.
- **Job**: title, company, location, salary min/max/currency (if any), job type, posted date, url(s), source(s), full JD text snapshot, fetched_at, dedupe_key, hidden (bool), hidden_reason.
- **MatchResult**: job_id, total score (0–100), breakdown JSON (per category: points, max, matched items, missing items), hard-gate flags, scored_at, method (`quick` or `deep`).
- **FilterRule**: type (title_contains, company_equals, min_years_over, min_salary_below, keyword_in_jd), value, action (hide), enabled.
- **Application**: job_id, status (`Saved`, `Applied`, `Interview`, `Offer`, `Rejected`, `Withdrawn`), applied_at, follow_up_at, notes, resume_version_id, cover_letter_version_id.
- **StatusHistory**: application_id, from, to, changed_at.
- **Document**: job_id (nullable), type (`resume`, `cover_letter`, `interview_prep`, `deep_analysis`), version number, content JSON, rendered PDF path, source (`copy_paste`, `ollama`, `template`, `manual`), created_at.
- **AITask**: task type, job_id, generated prompt, pasted/received response, parse status, errors, created_at.
- **Automation**: key, enabled, mode (`manual` / `scheduled`), schedule (e.g. daily at a set time), last_run_at, next_run_at.
- **AutomationRun**: automation key, started_at, finished_at, result, items processed, error.
- **Notification**: type, message, link, read, created_at.

## 6. Features

### 6.1 Resume and Experience Bank
- Upload a PDF or DOCX. The parser produces a **draft** profile and Experience Bank items, shown in a review screen where I confirm or edit them before saving.
- Parsing can also run in Copy-Paste AI mode (see 6.6) for better accuracy on complex layouts.
- After import, **the Experience Bank is the source of truth.** Tailored resumes are always generated from the bank plus a template, never by editing the original PDF.
- I can keep several BaseResumes, each a selection of bank items.

### 6.2 Job sources
- **JobStreet** (Malaysia first, built so other country sites can be added): a custom module calling the public, logged-out search endpoint the website itself uses. Research it carefully, keep it isolated, and handle schema changes gracefully.
- **LinkedIn, Indeed, Glassdoor** via `python-jobspy` (logged-out). Use `country_indeed="Malaysia"` where relevant. Glassdoor coverage for Malaysia may be thin; detect this and report it rather than fail.
- **Manual import**: paste a job URL (try to fetch and extract; if that fails, fall back to the next option) or paste the JD text with title and company. This must always work, even when every scraper is broken.
- Plugin interface: every source implements `fetch(search_profile) -> list[NormalizedJob]`. One failing source must never break the others.
- Hiredly and MauKerja are **out of scope for v1**, but the interface must make adding them easy.

### 6.3 Scraping safety (mandatory, on by default)
- No login, ever. No credential fields anywhere in the app.
- Default limits: each source runs at most 1–2 times per day, with a per-run cap on results (e.g. 30 for LinkedIn, 50 for others; configurable with safe maximums).
- Random delay between requests (e.g. 2–6 s), a realistic but honest user agent, sequential (not parallel) requests per source.
- Cache: never re-fetch a job detail already stored.
- On HTTP 429/403 or 3 consecutive errors, **auto-pause that source for 24 hours**, record the reason, and create a notification.
- Settings page shows each source's health: ok / error / paused (with the time it resumes).

### 6.4 Dedupe and filters
- Dedupe across sources with a fuzzy key from the normalized company name and job title (plus location). Merge into one Job with multiple source URLs.
- Filter rules (from 5. FilterRule) hide matching jobs automatically, e.g. a title containing "Senior" / "Lead" / "Manager", required years above X, certain companies or agencies, salary below a minimum. Hidden jobs stay viewable under a "Hidden" tab, with the reason shown.

### 6.5 Matching: quick score (rule-based, offline, automatic)
1. **Skill extraction**: match the skill dictionary (with aliases, case-insensitive, word-boundary aware) against the JD and the Experience Bank.
2. **Required vs preferred**: classify JD lines by section headings and phrases. Headings and phrases like "Requirements", "Qualifications", "Must have", "required" mean required. "Preferred", "Nice to have", "is an advantage", "is a plus", "bonus" mean preferred. Lines with no clear signal default to required.
3. **Rule checks** with regex/heuristics: years of experience ("3+ years", "minimum 2 years", "at least 1 year"), education (SPM / Diploma / Degree / Master + field), languages (English, Bahasa Malaysia / BM / Malay, Mandarin / Chinese), location vs my preferred locations (with a "Remote" option).
4. **Weights (total 100):**

| Category | Points |
|---|---|
| Required skills (fraction matched) | 45 |
| Preferred skills (fraction matched) | 15 |
| Years of experience | 20 |
| Education | 10 |
| Language + location | 10 |

   If the JD doesn't mention a category, give its full points and mark it "not specified".
5. **Hard gates**: if the required years exceed mine by 2 or more, or a mandatory language or degree is missing, mark the job ❌ and **cap the total at 40**.
6. Each item is labelled ✅ met / ⚠️ partial / ❌ not met, and the breakdown is shown in the UI so every point can be explained.
7. Weights and the gate thresholds can be changed in Settings.
8. Write thorough unit tests for the matcher using several realistic sample JDs.

### 6.6 AI: three modes (switchable globally in Settings, overridable per action)
- **Copy-Paste (default):** the system builds a complete prompt. I copy it, paste it into a free web chat (ChatGPT / Claude / Gemini), then paste the reply back. No API keys.
- **Ollama:** the same prompts are sent automatically to the local Ollama API. The model is selectable in Settings. Show a clear message if Ollama is not running or the model is not installed. Use generous timeouts and show progress.
- **Off:** AI features are hidden. Matching, tracking and the template cover letter still work.
- **There is no paid-API provider at all.**

**AI tasks:** `parse_resume`, `deep_analysis`, `tailor_resume`, `cover_letter`, `interview_prep`.

**Prompt construction:** task template (editable in Settings, stored as files under `backend/ai/templates/`) + relevant Experience Bank items **with their IDs** + JD snapshot + my profile basics + rules + the required output schema. A "Copy prompt" button copies it to the clipboard.

**Rules included in every prompt:**
- Use only facts from the provided Experience Bank. Never invent employers, dates, numbers, skills, or achievements.
- Every resume bullet must reference the ID of the bank item it was derived from.
- Put anything I lack under "gaps" or "suggestions"; never put it in resume content.
- Reply with exactly one JSON object inside a single ```json code block, matching the schema, with no extra commentary.

**Output schemas (define them as Pydantic models; these are the minimum fields):**
- `deep_analysis`: `{ requirements: [{text, type: "required"|"preferred", status: "met"|"partial"|"not_met", evidence_ids: [..], note}], overall_fit: 0-100, strengths: [..], gaps: [..], resume_suggestions: [..] }`
- `tailor_resume`: `{ summary, skills_order: [..], sections: [{section, items: [{source_id, text}]}], omitted_ids: [..], notes }`
- `cover_letter`: `{ greeting, paragraphs: [..], closing, used_ids: [..] }`
- `interview_prep`: `{ questions: [{question, category, why_likely, suggested_points_ids: [..]}] }`
- `parse_resume`: `{ profile: {...}, items: [{type, title, organization, start, end, bullets: [..], skills: [..]}] }`

**Tolerant parser + validation (shared by both modes):**
1. Extract the JSON from the reply (code block first, then the first balanced `{...}`). Repair common issues: trailing commas, smart quotes, stray text.
2. Validate against the Pydantic schema. On failure, show exactly which field is wrong, let me edit and re-paste, and offer a **"Generate fix-up prompt"** button that asks the AI to correct its own output.
3. **Fabrication guard:** flag in red any bullet whose `source_id` is missing or not in the bank, and any skill that is not in my bank or profile.
4. **Review screen:** side-by-side original bank text vs rewritten text. I can accept, edit or reject each item. Only accepted content is saved, as a new Document version.

**Cover letter template mode:** a fill-in-the-blanks template (company, role, top 3 matched skills, 1–2 chosen bank items) that works with AI off.

### 6.7 Documents and versions
- Each tailored resume, cover letter, interview prep and deep analysis is saved as a numbered version linked to the job.
- Render resumes and cover letters to PDF with a clean, **single-column, ATS-friendly** HTML template (standard headings, no tables or icons for core content, selectable text). Store PDFs under `data/documents/<job_id>/`.
- An Application records exactly which resume and cover letter version I sent. The Job Detail page shows these clearly.
- DOCX export is out of scope for v1.

### 6.8 Application tracker
- Statuses: Saved → Applied → Interview → Offer / Rejected / Withdrawn. Every change is recorded in StatusHistory.
- **Kanban view** (drag and drop between columns) and **table view** (sortable, filterable).
- Per application: notes, applied date, follow-up date (defaults to applied date + N days, configurable).

### 6.9 Skill Gaps page
- Aggregates the missing required and preferred skills across all saved jobs (and optionally all scored jobs above a threshold), ranked by frequency, with links to the jobs that ask for each skill. The purpose is to tell me what to learn next.

### 6.10 Automations (each has an on/off toggle and a manual/scheduled mode, plus a "Run now" button)
| Key | What it does | Default |
|---|---|---|
| `fetch_jobs` | Run enabled sources for each enabled SearchProfile | scheduled, daily |
| `score_new_jobs` | Quick-score jobs that have no score yet | scheduled, after fetch |
| `dedupe_and_filter` | Dedupe + apply filter rules to new jobs | scheduled, after fetch |
| `high_match_alert` | Notify for new jobs with score ≥ threshold (default 70) | on |
| `follow_up_reminder` | Notify when an Applied job passes its follow-up date | on, daily |
| `ollama_deep_analysis` | Run deep analysis via Ollama on new jobs ≥ threshold | **off** by default |

- Automations only use rule-based logic or Ollama, never Copy-Paste mode (it needs me present).
- **Catch-up:** automations run only while the app is running. On startup, any scheduled automation whose last run was missed runs once.
- Each run is logged in AutomationRun and shown on the Automations page.
- Notifications appear in the app (a bell with an unread count). Desktop notifications are optional and off by default.

### 6.11 Export and backup
- One-click export of jobs, scores and applications to Excel (`.xlsx`) and CSV.
- A "Backup" button copies `data/jobfinder.db` to `data/backups/` with a timestamp.

## 7. Frontend pages
1. **Dashboard**: counts by status, applications per week, response rate, new high-match jobs, unread notifications, source health summary.
2. **Jobs**: list of fetched and imported jobs with score, source, posted date, salary; filters and sort; "Hidden" tab; one-click Save to tracker; a "Fetch now" button.
3. **Job Detail**: JD snapshot, quick-score breakdown (✅⚠️❌), deep analysis (if any), AI action buttons (Deep analysis, Tailor resume, Cover letter, Interview prep) with the Copy-Paste flow (copy prompt → paste reply → validate → review → save), versions list, PDF download, notes, application status.
4. **Tracker**: Kanban and table toggle.
5. **Resume & Experience Bank**: upload + review parsed draft, edit bank items, manage BaseResumes.
6. **Skill Gaps**.
7. **Automations**: toggles, schedules, Run now, run log.
8. **Settings**: Profile, SearchProfiles, Sources (enable + health + limits), Filter rules, Scoring weights and gates, AI mode + Ollama model, prompt templates, skill dictionary, export/backup.

UI language: English. Keep the design clean and functional; speed of use matters more than looks.

## 8. Phases and acceptance criteria

### Phase 1: Core (usable without any scraping or AI)
- Project scaffold, `setup.bat`, `start.bat`, README with setup steps, git repo.
- Profile, resume upload + parse into a reviewable draft, Experience Bank CRUD, skill dictionary with seed data.
- Manual job import (paste JD; URL fetch as best effort).
- Quick-score matcher with breakdown + unit tests.
- Filter rules (applied to manual jobs too).
- Tracker (Kanban + table, status history, notes, follow-up date).
- Dashboard (basic), export to Excel/CSV, backup.
- **Done when:** I can upload my resume, paste a JD, see an explainable score with ✅⚠️❌, save the job, and move it through the tracker.

### Phase 2: Sources and automations
- JobStreet module, JobSpy module (LinkedIn/Indeed/Glassdoor), SearchProfiles, normalization, dedupe.
- All scraping safety rules from 6.3, source health UI.
- APScheduler automations from 6.10 (excluding `ollama_deep_analysis`), catch-up, run log, notifications.
- Skill Gaps page.
- **Done when:** with my search settings, "Fetch now" pulls Malaysian jobs from the enabled sources without login, duplicates are merged, filters hide what they should, new jobs are auto-scored, and a simulated 429 pauses that source for 24 h with a notification.

### Phase 3: AI and documents
- AI provider layer (copy_paste, ollama, off), prompt templates, tolerant parser, schema validation, fabrication guard, review screen.
- Tasks: parse_resume, deep_analysis, tailor_resume, cover_letter (+ template mode), interview_prep.
- Document versioning, ATS-friendly PDF export, linking versions to applications.
- `ollama_deep_analysis` automation.
- **Done when:** for a saved job I can copy a tailor-resume prompt, paste a free web chat's reply back, see any fabricated items flagged, accept the changes, and download a PDF; the same flow works automatically with Ollama.

## 9. How to work with me
- Start by restating your understanding in a few lines and listing any questions. Then propose the Phase 1 plan (files, modules, order of work) and **wait for my approval**.
- Ask before adding any dependency not listed in section 3.
- Write tests for the matcher, filters, dedupe, tolerant parser and fabrication guard. Run them before saying a step is done.
- After each phase: run the app, verify the acceptance criteria yourself, summarize what was built and how to use it, list known limitations, and commit.
- Keep files small and focused. Don't build features that are not in this brief. If something here turns out impractical (e.g. a site's endpoint changed), explain it and propose the simplest alternative instead of silently working around it.
