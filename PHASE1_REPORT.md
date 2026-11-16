# Phase 1 report

**Date:** 2026-11-07. **Status:** Phase 1 is complete. Phase 2 has not been started.

## 1. What was built

**Backend** (FastAPI + SQLModel + SQLite at `data/jobfinder.db`)

- **Profile:** includes editable years of experience (default 0) and degree status (completed / in progress) with an expected graduation date, as you asked.
- **Resume upload (PDF/DOCX):** produces a **draft** profile and Experience Bank items. Nothing is saved until you review the draft and click Save.
- **Experience Bank editing:** items get stable IDs (`B1`, `B2`, …) that are never reused. **BaseResumes** are named selections of bank items.
- **Skill dictionary:** 140 seeded tech and soft skills with aliases, editable in the UI. Matching is case-insensitive and respects word boundaries (Java ≠ JavaScript, C ≠ C++/C#, "the rest of" ≠ REST).
- **Manual job import:**
  - Paste a JD: always works.
  - Fetch from a URL: best effort. It prefers schema.org JobPosting data and, if fetching fails, falls back to the paste form with a clear message.
  - Duplicates are merged using a fuzzy company + title + location key.
- **Quick-score matcher** (weights 45 / 15 / 20 / 10 / 10):
  - Sorts JD lines into required, preferred or ignored (About us / Benefits).
  - Checks years, education level and field, languages and location.
  - Hard gates cap the score at 40.
  - Each item gets ✅ / ⚠️ / ❌ / ➖ with evidence: a bank ID or `profile` for skills, and the JD line for rules.
  - Weights and gates can be changed in Settings. Every job is rescored automatically when the profile, bank, skills or scoring settings change.
- **Filter rules:** title contains, company is, required years over, salary below, JD mentions. They apply to manual imports and are re-applied whenever a rule changes. Hiding or unhiding a job by hand overrides the rules.
- **Tracker:** statuses Saved → Applied → Interview → Offer / Rejected / Withdrawn. Every change is recorded in StatusHistory. Moving a job to Applied sets the applied date and a follow-up date (+7 days by default, configurable).
- **Dashboard:** counts by status, applications per week (CSS bars), response rate, follow-ups due, new high-match jobs, unread notifications, sources.
- **Export and backup:** Excel (`.xlsx` with Jobs and Applications sheets), CSV (jobs / applications), and a one-click database backup to `data/backups/`.

**Frontend** (React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + React Router): pages for Dashboard, Jobs (with Hidden tab), Job Detail, Tracker (Kanban with drag and drop, plus a table view), Resume & Bank, and Settings (Profile, Filter rules, Scoring, Skill dictionary, Export & backup).

**Scripts:** `setup.bat` (first-time install), `start.bat` (starts both servers and opens the browser), README, `DECISIONS.md` (28 logged decisions).

**Git:** local commits only, no remote.

## 2. How to use it

1. Run `setup.bat` once.
2. Run `start.bat`. It opens http://localhost:5730. Close the two console windows to stop the app.
3. **Resume & Bank** → upload your resume → fix the draft → **Save to Experience Bank**.
4. **Settings → Profile** → check years of experience, degree status / expected graduation, languages, preferred locations → **Save**.
5. **Jobs → + Import job** → paste a JD → **Import & score**. Read the breakdown on the job's page.
6. **Save to tracker**, then drag the card across the **Tracker** board (or change the status in table view).

The README has more detail.

## 3. Test results

| Suite | Result |
|---|---|
| Backend `pytest` (69 tests) | **69 passed** |
| Frontend `vitest` (5 tests) | **5 passed** |
| Frontend type-check + production build (`tsc -b && vite build`) | **OK** |

Backend tests per file:

| File | Tests |
|---|---|
| `test_matcher.py` (7 realistic fake JDs: junior React, senior Java, Mandarin-required IT support, remote fresh-grad Python, no-headings, Master's data scientist, inline headings) | 30 |
| `test_skills.py` | 10 |
| `test_dedupe_tracker.py` (dedupe key, JSON-LD extraction, tracker, dashboard maths) | 11 |
| `test_filters.py` | 7 |
| `test_resume_parser.py` (the same fake resume as plain text, generated DOCX and generated PDF) | 6 |
| `test_api_flow.py` (end-to-end over HTTP) | 5 |

All fixtures are fake (e.g. "Aisyah Tan", "Kedai Tech Sdn Bhd"). No real personal data is used anywhere.

## 4. Acceptance criteria checklist

I verified these by running `start.bat` and using the app in the browser pane with a fake resume and fake JDs.

| Criterion | Result | Evidence |
|---|---|---|
| Project scaffold, `setup.bat`, `start.bat`, README, git repo | ✅ PASS | `start.bat` started both servers and opened the app. A clean restart with an empty database seeded 140 skills and 2 filter rules. |
| Upload my resume | ✅ PASS | The fake PDF was uploaded through the file input and parsed into name, email, phone, location, Degree (in progress), languages, 7 skills, and 3 items (education / internship / project) with correct titles, organizations, dates, bullets and skills. After review it was saved as B1–B3 plus the BaseResume "Software Dev". |
| Paste a JD | ✅ PASS | The Import dialog was used to paste a junior React JD. It landed on the job page. |
| See an explainable score with ✅⚠️❌ | ✅ PASS | Score 65. Required skills 30/45 (4 of 6: TypeScript from B2, React from B2 + profile, JavaScript and Git from profile; HTML and CSS ❌). Preferred 0/15. Years 20/20 ("fresh graduates welcome"). Education 5/10 ⚠️ "Degree (in progress, expected Jun 2027)". Language + location 10/10. Text under "About Us" and "Benefits" (Python workshops, Chinese New Year, AWS sponsorship) was correctly ignored. |
| Save the job | ✅ PASS | "Save to tracker" created the application with status Saved. |
| Move it through the tracker | ✅ PASS | Kanban drag from Saved to Applied set the applied date (7 Nov) and follow-up date (14 Nov). The table view changed it to Interview. History shows new → Saved → Applied → Interview. Notes saved. |
| Filter rules apply to manual jobs | ✅ PASS | "Senior Java Engineer" was auto-hidden with reason `Title contains "Senior"`, shown under the Hidden tab with score 40 ❌ (years gate). |
| URL import as best effort, with fallback | ✅ PASS | A URL with no job posting showed "no job description was found… Paste the JD text instead" and kept the URL in the form. |
| Dashboard (basic) | ✅ PASS | Status counts, 100% response rate, weekly bars, and the high-match list showed the 95-score remote job. |
| Export to Excel/CSV and backup | ✅ PASS | The `.xlsx` has Jobs (3 rows) and Applications (1 row) sheets. Both CSVs downloaded. The backup created `data/backups/jobfinder-20261107-141750.db` containing 3 jobs. |

**Verification data:** the database from this run (fake data only) was moved to `data/verification-run-2026-11-07/`, so your first start is empty. Delete that folder whenever you like.

## 5. Known limitations

- **Resume parsing is heuristic.**
  - It works well for single-column resumes with clear headings (Experience, Projects, Education, Skills…).
  - Two-column PDFs, tables and creative layouts will need more manual fixing in the review screen. Scanned (image) PDFs have no text, and the app says so.
  - Copy-Paste AI parsing arrives in Phase 3.
- **The matcher only knows skills in the dictionary.** A JD skill that isn't in it (e.g. "Odoo") is invisible until you add it under Settings → Skill dictionary.
- **Required vs preferred is decided by headings and phrases.** Odd JDs can be misread (e.g. a "Bonus" heading that actually lists must-haves). The breakdown always shows what was decided, so you can spot it.
- **"Responsibilities" sections count as required** (the brief's default), so tools mentioned only there count as required skills.
- **The years heuristic takes the largest lower bound** among required clauses that mention experience. "Fresh graduates welcome" anywhere means 0 years.
- **Location matching is substring-based**, with a few aliases (KL, PJ, JB, KK, Penang). Wider areas aren't understood: preferring "Selangor" does not match a job in "Cyberjaya" or "Shah Alam" unless you add those towns too.
- **Short or ambiguous skill names** (Go, R, C, REST, Excel, Spring…) only match with dictionary capitalization. "Go" at the start of a sentence can still be a false positive.
- **URL import** works only for pages that serve the JD without JavaScript or a login (typically sites with schema.org JobPosting). LinkedIn, JobStreet and others may block it or need JavaScript; then you paste.
- **Phase 1 creates no notifications.** The unread count is always 0 until the Phase 2 automations.
- **The "Fetch now" button is disabled** until Phase 2.
- **`start.bat` runs dev servers** (Vite + uvicorn without reload). Close the two windows to stop. Ports are fixed at 5730 / 8730.
- **There are no database migrations yet.** If a later phase changes a table, I will add an explicit migration step (DECISIONS #2).

## 6. Things for you to decide or check

1. **Ports.** Another project on this laptop was already on port 5173, so JobFinder uses **5730 (UI) / 8730 (API)** (DECISIONS #26). Tell me if you'd prefer other ports.
2. **Default filter rules.** The seeds are `title_contains: Senior, Lead, Manager, Principal, Head of` (on) and `min_years_over: 3` (off). Adjust them in Settings → Filter rules.
3. **Scoring choices to confirm** (all in DECISIONS #10–#15):
   - **Responsibilities:** counted as required. The alternative is to ignore them.
   - **Computing degrees:** CS, SE and IT count as one family.
   - **Field mismatch:** halves the education points.
   - **Language points:** the fraction of mentioned languages you speak.
4. **Profile skills.** Skills from your resume's Skills section are stored on your profile and count as evidence (shown as `profile`). The alternative is to accept only skills backed by a bank item. Profile skills are the generous option; bank-only would be stricter.
5. **Follow-up default** is 7 days, and the **high-match threshold** is 70. Both can be changed in Settings → Scoring.
6. **Verification data** in `data/verification-run-2026-11-07/`: keep it or delete it.

## 7. Commits

See `git log`. Milestones: backend core; frontend + verification fixes + report.
