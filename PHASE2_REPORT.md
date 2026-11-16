# Phase 2 report: sources and automations

**Date:** 2026-11-08, updated 2026-11-13. **Status:** built and tested offline. **Smoke test step A (JobStreet) ran on 13 Nov and was stopped on HTTP 403; see section 6.** Steps B and C have not run. No request was made to any job site during development. Phase 3 has not started.

## 1. What was built

| Area | What you get |
|---|---|
| **JobStreet source** | The public, logged-out search and job-detail endpoints the JobStreet website itself calls. Malaysia is configured; other country sites are one table row each. Every field is read defensively. A changed response shape shows "schema changed", and the response is saved to `data/debug/`. If a job's details can't be read, it is saved from its search summary, clearly marked. |
| **JobStreet links** (decision #41) | Pasting a JobStreet job link into Import job takes the job ID and fetches it through the JobStreet module: one request, with the same pause rules. A job that's already saved isn't fetched again. |
| **LinkedIn / Indeed / Glassdoor** | Through JobSpy, one site at a time, using Malaysia location strings and `country_indeed="malaysia"`. Glassdoor is off by default. If it runs and finds little or nothing for Malaysia, that's reported as a note, not a failure. **LinkedIn job descriptions are fetched by us, not JobSpy** (after your review): one public job page per *new* job, 2–6 s apart, and a 403/429/999 or a login-wall redirect pauses LinkedIn. JobSpy's logged-only warnings are captured, and signs of throttling count as rate-limited. |
| **Shared pipeline** | Every fetched job goes through the *same* code as manual import: dedupe → filters → description snapshot → quick score. Duplicates across sites merge into one job, with all links, sources and site IDs. |
| **Scraping safety** | No logins anywhere. One request at a time, 2–6 s apart. Per-run and per-day limits with hard maxima. Details already stored are never fetched again. **429/403 pauses that source for 24 h at once**, as do 3 failed runs in a row; you get a notification and the reason is shown. One failing source never stops the others, and jobs fetched before a failure are kept. |
| **Search profiles** | "KL/Selangor" and "Sabah" (keywords "software engineer", "software developer", "full stack developer"; Full time; last 7 days). Editable in Settings → Search profiles. |
| **Automations** | `fetch_jobs` (**off**, 09:00). `dedupe_and_filter`, `score_new_jobs` and `high_match_alert` run right after each fetch. `follow_up_reminder` runs daily at 09:00. Each can be on/off and scheduled/manual-only, and has Run now. Every run is logged. A daily run missed while the app was closed runs once at startup. |
| **Notifications** | A bell with unread count: high-match jobs (once per job), follow-ups (once per follow-up date), sources paused. |
| **Skill gaps** | Missing required and preferred skills across your tracker jobs (or all jobs above a score), ranked, with links to the jobs. Soft skills are listed separately. |
| **Screens** | Fetch now dialog (choose sources, profile and an optional per-source cap; live per-source results). Automations page with run log. Skill gaps page. Settings → Search profiles and Job sources (health, limits, Resume now). Real source health on the Dashboard. |

## 2. Test results

| Suite | Result |
|---|---|
| Backend `pytest` | **297 passed** (after the 13 Nov fixes). An autouse guard makes any real HTTP request or real JobSpy call fail, so this also shows that no test touched the network. |
| Frontend `vitest` | **21 passed** |
| Type-check and production build | OK |

New Phase 2 tests cover:
- the polite client (delays, user agent, 429/403 handling)
- source health (daily limits, 24 h pause, 3 errors in a row, auto-lift, clamped limits)
- JobStreet (normalising, filters, cap, no re-fetching, summary fallback, a mocked 429 halfway that still keeps earlier jobs, schema change saved to `data/debug/`, URL import, URL import pausing on 429)
- JobSpy (row mapping, call arguments, error classification, Glassdoor coverage)
- LinkedIn safety: descriptions fetched by us and paced (including before the first page); known jobs not requested; 429/403/999 or a login-wall redirect on a job page stops at once and **pauses LinkedIn for 24 h** while keeping earlier jobs; throttling warnings, logged-only warnings and mostly-empty batches count as rate-limited; warnings reach the run log
- the runner (all sources through the shared pipeline, cross-site merge, second run fetches nothing new, a 429 pausing one source while others continue, cap override, single-profile smoke shape)
- automations (catch-up rules, scheduler registration, chaining, alerts once, reminders once per date, duplicate merge keeping the tracker entry)
- every Phase 2 API, and Skill gaps

**Browser check** (test copy, scratch data, `JOBFINDER_FAKE_SOURCES=1`, your database untouched):
- Fetch now with 3 sources gave 7 new jobs; the JobStreet/LinkedIn and JobStreet/Indeed twins merged, and Senior/Lead roles were hidden.
- A simulated 429 on Indeed paused it until +24 h. Settings showed "Resume now", and the bell showed the notification.
- I also checked the Automations page with its run log, Skill gaps, and Dashboard source health.

That check found three problems, now fixed:
- A second search profile re-fetched the same jobs' details in one run.
- The bell's panel was hidden behind page content.
- The paused source card was squashed.

## 3. Decisions for you to review

All are in `DECISIONS.md` #78–114. The ones worth a look:

1. **#79 User agent.** Our own JobStreet client says it's JobFinder, behind a browser-style prefix. JobSpy uses its own browser-like headers, as you accepted.
2. **#80 What a "run" is.** A run is one Fetch per source, covering *all* search profiles. It counts toward the daily limit when it starts, even if it fails. A failed attempt therefore uses up a run, which is the safe direction.
3. **#82 / #83 / #96 Request volume.** With your two default profiles, a full JobStreet run is up to 9 searches (3 keywords × KL, Selangor, Sabah; "Remote" is skipped for JobStreet) plus one detail request per new job (≤ 50). At 2–6 s each that's up to about 4 minutes in the background.
4. **#86 Fetch now while `fetch_jobs` is off.** Fetch now and Run now still work; "off" only stops the *schedule*. I chose this so the supervised test is possible.
5. **#92 / #93 LinkedIn descriptions and throttling.** LinkedIn needs one job-page request per *new* job; we make it ourselves, paced and watched. JobSpy's silent throttling signals now pause a source. The empty-description rule (over 60% of a batch of 3+) could, in theory, pause Indeed if Indeed legitimately returned few descriptions. If that happens during the smoke test, tell me and I'll adjust the threshold.

## 4. Supervised smoke test procedure (do this with me present)

**Goal:** confirm the real endpoints and response shapes with as few requests as possible. **Stop immediately on any 403/429.**

### Before you start
1. Close both JobFinder windows and run `start.bat`.
   - The database gets new columns and tables automatically.
   - Jobs are rescored.
   - `fetch_jobs` stays **off**.
2. Optional but recommended: Settings → Export & backup → **Backup database now**.
3. Settings → Search profiles → **Add a search profile**:
   - Name `Smoke test`, keyword `software engineer` (only one), location `Kuala Lumpur` (only one), Full time, last 7 days, no sources ticked.
   - Save. This makes each source do **one** search.
4. Tell me you're ready. I'll watch the backend console and run log with you.

### Step A: JobStreet (expected about 6–7 requests)
1. Jobs → **Fetch now**.
2. Untick everything except **JobStreet**.
3. Search profile: **Smoke test**.
4. "Limit each source to" **5**.
5. Click **Fetch from 1 source**.

Request budget: **1 search + up to 5 detail requests**. If the detail call (GraphQL) doesn't work, it switches once to the job pages, so at most 1 more request. Expect 1–2 minutes because of the 2–6 s pauses.

What to watch:
- **Good:** "jobstreet: ok: 5 fetched, 5 new …" and a request count of about 6. Lines starting "JobSpy warning:" only appear for the JobSpy sites; read them out to me if there are any. Open one job: it should show the full description, not "Summary only".
- **"Summary only" on the jobs:** the search worked but details didn't. Tell me; the detail response is saved in `data/debug/`.
- **"schema changed … saved to data/debug/…":** the endpoint answered in a different shape. Tell me the file name and I'll fix the parser from it. Don't fetch again.
- **"paused" / 429 / 403:** STOP. Don't resume, and don't try another source. Tell me the exact message.

### Step B: Indeed (expected about 1–2 requests)
Same as step A, but tick only **Indeed**. Budget: 1–2 calls (Indeed's API returns descriptions with results). Watch for the same outcomes.

### Step C: LinkedIn (expected about 6 requests)
Same as step A, but tick only **LinkedIn**. Budget: **1 search page** (JobSpy) **+ up to 5 job pages** fetched by JobFinder itself, 2–6 s apart. The run log's request count should be about 6.
- LinkedIn is limited to **1 run per day**, so this uses today's run.
- LinkedIn is the site most likely to answer 429 or redirect to its login page; either one pauses LinkedIn for 24 h, which is fine. **Stop there and tell me the message.**
- Also check that the LinkedIn jobs show a full description, not "Summary only". If they show "Summary only", the job page layout differs; it's saved in `data/debug/` for me.

### Glassdoor: skip
It stays off. If you're curious later, a run is expected to say "little or no Malaysia coverage".

### Total
About **13–15 requests** to job sites across the whole test, one source at a time, each at least 2 s apart.

### After the test
- Check **Jobs**: new jobs with scores; the same job from two sites should appear once, showing both sources.
- Check **Automations → Run log**: one entry per step, with each source's result and request count.
- Then decide whether to **turn on `fetch_jobs`** (Automations page). It runs daily at 09:00 with all enabled search profiles.
- You can delete the "Smoke test" profile afterwards.

## 5. Known limitations

- **JobStreet's API shape is unconfirmed** until step A. If it differs, the fix is a parser change from the saved response, not more requests.
- JobSpy may change how it reaches LinkedIn, Indeed or Glassdoor in future versions. It's pinned to 1.4.1.
- Automations run only while JobFinder is open; missed daily runs catch up once at the next start.
- Desktop notifications aren't built (optional in the brief); only in-app notifications are.
- The fetch runs in the background inside the backend process. Closing the backend window mid-fetch stops it. Jobs already saved stay, and the run log shows the run as unfinished.
- Hiredly and MauKerja are out of scope for v1. The source interface is ready for them.

## 6. Smoke test step A result (2026-11-13)

**Result:** "jobstreet: paused: Stopped on HTTP 403 from my.jobstreet.com … 0 fetched … (4 request(s))". The run took 10.6 s. JobStreet is paused until 14 Nov 10:26 (Malaysia time). As agreed, nothing else was run.

**Requests made (reconstructed).** There was no request log yet: the backend console only shows local API calls, and nothing was saved. The sequence below is the only one the code allows with 4 requests, 0 jobs saved and no `data/debug/` file:

1. `GET https://my.jobstreet.com/api/jobsearch/v5/search?siteKey=MY-Main&sourcesystem=houston&keywords=software+engineer&page=1&pageSize=5&locale=en-MY&where=Kuala+Lumpur&daterange=7` → **200**. Cards came back, but the job-type/date filters removed some, leaving fewer than 5.
2. The same search with `page=2` → **200**. This was the paging bug (#100).
3. `POST https://my.jobstreet.com/graphql` (`jobDetails`, first card) → **failed, but not with 403/429**. It was another 4xx/5xx or a non-JSON answer; a changed JSON shape would have left a file in `data/debug/`. The note saying why was dropped from the message (#101).
4. `GET https://my.jobstreet.com/job/<first card id>` (the page fallback) → **403**. Because this was the first card, nothing had been collected yet, and the cards were thrown away (#99).

**Fixed offline** (decisions #97–101): block and error responses are saved; every request is logged; cards survive a block as "Summary only"; a cap of 30 or less means one search; notes are kept in the run log. The tests reproduce this exact sequence.

### Your decision and the next live steps

**B, falling back to A** (decisions #102–104).
- JobStreet details now come only from GraphQL. The job page is never requested.
- Summary-only jobs are never retried automatically.
- Their scores show as **rough**, and they're left out of high-match alerts.
- **Open & paste full JD** on such a job updates it in place and rescores it.

**Before any live step, restart JobFinder:** close both windows, then run `start.bat`, so the new code runs.

- **Today, Step B: Indeed only, Smoke test profile, limit 5.**
  - Budget: 1–2 JobSpy calls.
  - Indeed's requests are made by JobSpy, not our client. A block shows in the run log as a JobSpy error or "JobSpy warning: …"; it isn't a saved response file.
- **Today, Step C: LinkedIn only, Smoke test profile, limit 5.**
  - Budget: 1 JobSpy search plus up to 5 job pages from JobFinder.
  - Job pages are logged in `data/logs/requests.log`. A block or login-wall redirect is saved to `data/debug/`.
- **From 14 Nov 10:26, the JobStreet check: Smoke test profile, limit 1.**
  - Exactly **1 search + 1 details request**.
  - If the details request is refused or fails, the response is in `data/debug/`, the job is kept as a summary, and we stay on option A.

Stop on any block, as before.

## 7. Smoke test step B result (2026-11-13)

**Indeed answered normally:** no block and no throttling warnings. But two things went wrong:
- **34 jobs** were saved instead of at most 5. The limit box was empty, so Indeed's own limit of 50 applied. JobSpy asked for 50 and got 34, in **1 request**.
- **Fetch was clicked twice.** The second run (1 request) found nothing new and used Indeed's second run for today.

**Fixed offline** (decisions #105–110):
- The limit defaults to 5 and is remembered.
- An empty limit is spelled out on the button.
- A second fetch the same day asks first.
- A running source can't be fetched again.
- The run log shows the limit and profile actually used.
- A JD with no recognised skills gets a low-confidence score capped at 50, with no alert.
- There's a new "Title must contain one of" filter, off by default.
- Indeed locations are tidied.

**Dry run on a copy of your database** (then deleted):
- Locations: all 33 Indeed jobs went from "…, M14, Malaysia" to the plain place name.
- Low confidence: 3 jobs with no recognised skills dropped from 40 to 25.
- Draughtman still scores **100**. Its JD matches "Git" through the alias "Version control" (#110).
- A QA Engineer job and Site Reliability Engineer II stay at **92**. Indeed's text has no "Requirements" heading, so every skill counts as *preferred*, and the empty *required* category gets full points.
- Turning on the allow-list would hide Draughtman, Production Technologist, Digital Transformation Product Owner and 4 others.

## 8. Smoke test step C result and scoring fixes (2026-11-13)

**Step C (LinkedIn, limit 5):** ok, 6 requests.
- Every job page answered 200 and came back with a full description.
- 1 job merged with an existing one.
- 3 of the 4 new jobs were Senior roles, and the 4th hit the years gate. That led to the new entry-level default keywords (#111).

**Scoring fixes** (#112–114), measured on a copy of your database (deleted afterwards):

| Job | Source | Before | After | Why |
|---|---|---|---|---|
| Draughtman | Indeed | 100 | **50, low confidence** | "Version control" no longer means Git, so no skills are left |
| A QA Engineer job | Indeed | 92 | **78** | No requirements section: its skills now count as required (2 of 4 matched) |
| Site Reliability Engineer II (Platform) | Indeed | 92 | **76** | Same; "Job description" isn't a requirements heading (5 of 11 matched) |
| SENIOR MANUAL QA ENGINEER | Indeed | 90 | **62** | Same (1 of 2 matched) |
| Senior Fronted Engineer | Indeed | 85 | **74** | Same (7 of 9 matched) |
| Production Technologist | Indeed | 25, low confidence | 25, low confidence | Unchanged: still no skills |

All other jobs keep their scores.

**Still high:** Tech Refresh Team Lead (Indeed) scores 100. It names one skill, which you have, and it states an education level (SPM), so it isn't "thin". The title allow-list hides it. "Team Lead" is also caught by the existing Lead filter, so it's already hidden.

**Default keywords:** your KL/Selangor and Sabah profiles move to the new entry-level keywords at the next start. Smoke test is left as it is.
