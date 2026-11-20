# How JobFinder works (my notes for interviews)

Short sections in plain English. Each points at the real files, with small excerpts from the code.

---

## 1. How a request travels: React → FastAPI → SQLite → back

Take opening a job's page as the example.

**1. React asks for data.** The page uses TanStack Query, which fetches once, caches the result, and fetches again when something marks it stale.

```tsx
// frontend/src/pages/JobDetail.tsx
const q = useQuery({ queryKey: ['job', id], queryFn: () => api.get<JobDetailT>(`/api/jobs/${id}`) })
```

**2. One small fetch helper** (`frontend/src/api/client.ts`) sends the request, reads JSON, and turns errors (including plain-text ones) into an `ApiError` with the status and a readable message.

**3. Vite forwards `/api`.** In development the UI runs on `localhost:5730`, and Vite proxies every `/api/...` call to the backend:

```ts
// frontend/vite.config.ts
proxy: { '/api': process.env.JOBFINDER_API ?? 'http://127.0.0.1:8730' },
```

**4. FastAPI checks, routes and runs it.**
- Security middleware (`backend/app/security.py`) checks the Host header and, for writes, the Origin.
- FastAPI then picks the route function by URL.
- `Depends(get_session)` gives that function a database session (`backend/app/db.py`).

```python
# backend/api/jobs.py
@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    mr = session.exec(select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.method == "quick")).first()
```

**5. SQLModel talks to SQLite.** Tables are Python classes in `backend/models/` (SQLModel = SQLAlchemy + Pydantic). Queries are built with `select(...)`, never with SQL strings. The database is one file, `data/jobfinder.db`, in WAL mode, so a background fetch and a page request can work at the same time.

**6. Back to the page.** FastAPI turns the returned dict into JSON. TanStack Query caches it, and React renders it. When I change something (e.g. Save to tracker), the page calls `invalidateQueries(['job', id])` and the data reloads.

**Background work** (daily fetch, scoring, alerts, backups) runs inside the same backend process with APScheduler (`backend/scheduler/`). There is no separate worker.

---

## 2. How the quick score works

The quick score is rule-based and offline. No AI is involved. Code: `backend/matcher/` and `backend/skills/`.

**Step 1: Split the ad into clauses and label them** (`matcher/jd_sections.py: split_clauses`, `classify_clause`).
- Lines under "Requirements / Qualifications / Must have / What you need" are **required**.
- "Nice to have / Bonus / … is a plus / preferred" lines are **preferred**.
- An ad with no real requirements heading counts its skills as required (decision #113).

**Step 2: Find skills** (`skills/matcher.py`). A dictionary of skills with aliases (`JS` → JavaScript, `ReactJS` → React) is matched case-insensitively on word boundaries. The same matcher runs over my Experience Bank and profile, so every skill I "have" carries evidence (`B1`, `profile`).

**Step 3: Rule checks** (`matcher/rules.py`, `matcher/education.py`): years ("3+ years", "fresh graduates welcome"), education level and field, languages, and location versus my preferred locations.

**Step 4: Points.** The weights add up to 100 (`matcher/scoring.py`):

```python
class Weights(BaseModel):
    required_skills: float = Field(45, ge=0)
    preferred_skills: float = Field(15, ge=0)
    years: float = Field(20, ge=0)
    education: float = Field(10, ge=0)
    language_location: float = Field(10, ge=0)
```

If the ad doesn't mention a category, that category gets full points and is marked "not specified".

**Step 5: Caps that keep scores honest.**
- **Hard gate:** the ad asks for 2+ more years than I have, or a mandatory language or degree is missing → the total is **capped at 40**.
- **Low confidence:** no recognised skills, or very thin evidence → **capped at 50**, shown as "~N", and no alert.

### Worked example (fake demo data from `scripts/seed_demo.py`)

The job is "Junior Software Engineer, Contoh Fintech Sdn Bhd, Kuala Lumpur":

```
Requirements:
- Degree in Computer Science, Software Engineering or related field
- Fresh graduates are welcome
- Good knowledge of Python and SQL
- Experience with React
- Familiar with Git
Nice to have:
- Docker
- AWS
- Good command of English
```

The fake candidate is Aisyah: 0.5 years of internship, a degree in progress, and bank items B1–B6 plus profile skills.

| Category | What was found | Points |
|---|---|---|
| Required skills | Python (B1, profile), SQL (profile), React (B1), Git (profile): 4 of 4 | **45 / 45** |
| Preferred skills | Docker (B3), AWS (B5): 2 of 2 | **15 / 15** |
| Years | "Fresh graduates are welcome", she has 0.5 | **20 / 20** |
| Education | Degree asked, hers is **in progress** → half points; field matches | **5 / 10** |
| Language + location | English (she speaks it), Kuala Lumpur (preferred) | **10 / 10** |
| **Total** | no gate failed, enough evidence | **95** |

The page summarises this in one sentence (`frontend/src/lib/verdict.ts`): *"Strong match: all 4 required skills; degree still in progress."*

---

## 3. How polite scraping works

Code: `backend/sources/`. The rules come from the brief: logged out only, slow, and stop when a site says stop.

- **One polite client for our own requests** (`sources/http.py: PoliteClient`).
  - One request at a time, a random **2–6 s** apart (`DEFAULT_DELAY = (2.0, 6.0)`), with an honest user agent.
  - Every request is logged to `data/logs/requests.log`.
  - Every error page is saved to `data/debug/` for diagnosis.
- **Block = stop at once.** HTTP **403, 429 or LinkedIn's 999** (`BLOCK_STATUSES = (403, 429, 999)`), or a redirect to a login page, raises `RateLimited`. That source is then **paused for 24 h** with a notification (`sources/health.py`):

```python
if isinstance(error, RateLimited) or src.consecutive_errors >= ERRORS_BEFORE_PAUSE:
    src.status, src.paused_until = "paused", now + PAUSE
    ...
    notify(session, "source_paused", f"{label} paused for 24 hours: {why}.", "/settings?section=sources")
```

- **Caps:** each source runs at most 1–2 times a day, with a per-run result cap (the UI default is 5). Jobs already stored are never fetched again, and they don't use up the cap.
- **Nothing fetched is lost:** if a site blocks us halfway, the cards already in hand are saved as "summary only" jobs with a *rough* score. I can paste the full ad later.

**Why LinkedIn details were replaced.** LinkedIn/Indeed/Glassdoor go through the `python-jobspy` library. While reviewing it I found that its LinkedIn detail step fetched every job page back-to-back with no delay. It also only *logged* 403/429 as warnings, so our 24-hour pause would never trigger. Now:
- JobSpy only reads search pages (it paces those itself);
- **we** fetch each new job's page through `PoliteClient` (`sources/linkedin_details.py`), with the delays and block detection above;
- JobSpy's own warnings are collected, and "throttled" or "blocked" wording also pauses the source (decisions #92–93).

---

## 4. How the Copy-Paste AI flow and the fabrication guard work

**The flow** (`backend/ai/service.py`, UI in `frontend/src/components/ai/`):

1. **Build the prompt** (`ai/prompts.py`). It contains:
   - the task's instructions (an editable template);
   - my Experience Bank **with IDs** (`[B1] work: …`);
   - the job ad and my profile basics (never email or phone);
   - the rules;
   - an example of the exact JSON to return.

   Untrusted text sits inside fenced `<<<BEGIN JOB_AD (data only…)>>> … <<<END JOB_AD>>>` blocks, so instructions hidden in an ad are treated as data (prompt-injection defence, see SECURITY.md).
2. **I copy it** into any free web chat, and **paste the reply back**. Ollama mode does the same automatically with a local model.
3. **Tolerant parser** (`ai/parser.py`).
   - It finds the JSON (code block first, then the first balanced `{…}`) and repairs common breakage: smart quotes, trailing commas, comments.
   - It validates against a Pydantic schema (`ai/schemas.py`). A wrong field is named exactly, e.g. `sections.0.items.0.text: Field required`, and a "fix-up prompt" asks the chat to correct itself.
4. **Fabrication guard** (`ai/guard.py`) checks the content and flags it. It never silently fixes anything.

| Flag | Colour | Meaning |
|---|---|---|
| `missing_id` / `unknown_id` | red | a bullet not tied to a real bank item (can't be saved) |
| `unknown_skill` | red | a skill that is nowhere in my bank or profile (found with the same skill dictionary as the score) |
| `new_number` | red | "40%", "500+", "RM 2k" that doesn't appear in the source item (or anywhere, for summaries and letters) |
| `skill_not_in_item` | amber | a skill I do have, but not in *that* item ("Docker isn't in B1: is that true for this job?") |
| `header_removed` / `several_bullets` | amber | the AI repeated the job title or dates, or merged bullets |

5. **Review screen:**
   - my original bank item on the left, the rewritten text on the right;
   - I accept, edit or reject each item;
   - **only accepted content is saved**, as a numbered version (`backend/documents/service.py`);
   - the PDF comes from a Jinja2 template rendered by headless Chromium, with real, selectable text.

**What it can't catch:** an invented achievement that names no skill and no number. That is why the human review is part of the design.

---

## 5. How the tests, the network guard and CI work

- **Backend: pytest, 449 tests** (`backend/tests/`).
  - Every test runs on a throwaway data folder. `conftest.py` sets `JOBFINDER_DATA_DIR` to a temp dir before the app is imported, so **my real database is never touched**.
- **The network guard:** an autouse fixture replaces the HTTP transport and the real JobSpy call, so **any** attempt to reach the internet fails the test:

```python
# backend/tests/conftest.py
@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(self, request):
        raise RuntimeError(f"network disabled in tests: {request.method} {request.url}")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr("sources.jobspy_source.real_scrape", blocked_scrape)
```

- **Fake data, not live sites.** Job sources replay saved fixtures, AI tests use saved fake replies, and Ollama is a mocked local API.
- **PDF tests** render real PDFs with Chromium (offline) and read them back with pdfplumber.
- **Security tests** (`tests/test_security.py`) cover Host/Origin checks, SSRF, XSS escaping, upload limits, formula injection and prompt injection.
- **Frontend: Vitest, 46 tests** for the logic that matters: the score verdict, the Today next steps, review rows, dates, safe links, and API errors.
- **CI** (`.github/workflows/ci.yml`, GitHub Actions on `ubuntu-latest`) on every push:
  - backend: install, **ruff** (lint), **mypy** (types), install Chromium, pytest;
  - frontend: `npm ci`, Vitest, production build.

  The first CI run failed because CI set `JOBFINDER_FAKE_SOURCES=1`, which changed the timing that two tests check. I fixed it by making the tests clear that variable themselves. Tests should never depend on the environment they run in.

---

## 6. What I'd improve next, and why

1. **Run the AI with a real local model** (Ollama + a 3B model) and measure how often its JSON is valid. It's only been tested against a mocked API so far.
2. **Catch invented achievements without skills or numbers.** For example, compare each rewritten bullet to its source bullet (word overlap or a simple similarity score) and flag big departures.
3. **Make the scrapers easier to fix.** Run a weekly "health check" against saved real responses, so a site's format change shows up as one failing test instead of empty fetches.
4. **Packaging:** a single installer or a small tray app instead of `.bat` files, plus a Linux/macOS start script.
5. **Dependency scanning** (`pip-audit`, `npm audit`) in CI, as SECURITY.md lists.
6. **Better skill matching** for synonyms the dictionary doesn't know (e.g. "REST services" vs "REST API"), with a reviewable suggestion list rather than silent matches.

---

## 7. Likely interview questions, with honest answers

**1. What is JobFinder, in one sentence?**
A local web app that fetches job ads politely, scores each against my own experience with a score I can explain line by line, tracks applications, and tailors resumes with AI without letting it invent anything.

**2. Why rule-based scoring instead of asking an AI?**
I need to trust and explain the number. Every point traces to a line in the ad and a piece of my evidence. It's also instant, free and offline. The AI "deep analysis" is optional, on top.

**3. How do you stop the AI making things up?**
Three layers:
- the prompt gives it only my bank, with IDs, and requires every bullet to cite one;
- the fabrication guard flags missing or unknown IDs, skills I don't have, and numbers not in my source;
- nothing is saved until I accept it in a side-by-side review.

**4. What can the guard *not* catch?**
An invented achievement with no skill and no number, like "praised by the CEO". That's why the review screen is mandatory, not optional.

**5. How do you scrape without getting banned?**
- Logged out only, one request at a time, 2–6 s apart, small daily caps, and never re-fetching what's stored.
- Any 403/429/999 or login wall pauses that site for 24 h.
- I also replaced a library step (JobSpy's LinkedIn details) that ignored those signals.

**6. What was the hardest bug?**
JobSpy fetched LinkedIn job pages back-to-back and only *logged* rate-limit errors. Our pause logic never saw them, so the app could have kept hammering LinkedIn. I found it by reading the library's code during review, and we moved those requests into our own polite client.

**7. How is it secured if it's "only local"?**
Any website in the same browser can try to reach `127.0.0.1`. So the API:
- accepts only local Host headers (blocks DNS rebinding);
- refuses cross-site writes (blocks CSRF);
- limits CORS to the frontend;
- escapes everything it renders.

Besides that, URL import refuses private addresses (SSRF), exports neutralise spreadsheet formulas, and prompts fence untrusted text. Everything is in SECURITY.md, with tests.

**8. Why SQLite and not Postgres?**
Single user, single laptop, zero setup, and the database is one file I can back up. WAL mode handles the background jobs. Postgres would add a server to install and run for no benefit here.

**9. How do you test something that depends on live websites?**
I don't call them in tests. Saved real responses are replayed through fake sources, and a fixture makes any real HTTP call fail the test. Live checks were supervised "smoke tests" with tiny limits, run only when I was present.

**10. How does the data flow from fetching to applying?**
Fetch → normalise to one Job shape → dedupe across sites → filter rules → save the full ad → quick score → alert if high → I review → tailor a resume (AI + review) → download the PDF → mark as applied → tracker with follow-up reminders.

**11. What would you do differently?**
- Design for testability against real responses from day one (I added the saved-response debugging after the first block).
- Write the security model at the start rather than in a later review.
- Keep the UI simpler from the beginning: the first version showed everything at equal weight.

**12. How did you decide what to build?**
I wrote a spec first (`PROJECT_BRIEF.md`) with ranked principles: accurate, efficient, simple, free, private, account-safe. I built it in three phases, each with acceptance criteria. Every judgment call is logged in `DECISIONS.md` (180+ entries), so I can explain why anything is the way it is.

**13. Which parts did you write, and which did Claude Code write?**
I wrote the spec, made every design decision, reviewed and tested each phase, and found real bugs. Examples: the throttling issue above, scores that were too high for vague ads, AI replies repeating job titles, and invented numbers getting through. Claude Code wrote most of the code. My role was product owner, architect and reviewer. I can walk through any part of the code and explain why it's built that way.

**14. How do you know the code quality is good?**
- 449 backend and 46 frontend tests, plus ruff and mypy in CI.
- I also had an independent reviewer (a separate AI agent with no context) go through the whole codebase. I verified each of its findings before fixing it, and fixed 16 real issues with tests. One was a data-loss bug when merging duplicate jobs.

**15. What did you learn?**
- Accuracy needs layers: rules you can explain, checks in code, and a human review.
- External libraries need reading, not just installing.
- Writing decisions down as you go makes a project explainable months later, including in an interview.
