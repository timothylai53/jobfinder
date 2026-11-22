# JobFinder: standing rules

Personal, single-user job finder (see `PROJECT_BRIEF.md`). Phases 1–3 are done; reports are in `PHASE*_REPORT.md`, every judgment call is in `DECISIONS.md`.

## Rules for every session

1. **No live requests.** Never make requests to job sites or AI websites unless the user is present and has explicitly started a supervised live step. Tests use fixtures, fake AI replies and a mocked Ollama API (`backend/tests/conftest.py` blocks real HTTP).
2. **Hands off the real database.** Never read, write or run anything against `data/jobfinder.db` except through the app the user runs. For checks, use a temporary copy or a scratch database, and delete it afterwards.
3. **No personal data in the repo.** Never put the user's real resume or personal details in fixtures, tests or commits. Use fake people and data (e.g. "Ali Bin Contoh", "Syarikat Contoh Bhd").
4. **Decisions, tests, commits.**
   - Log every judgment call in `DECISIONS.md` (next number, decision, reason).
   - Run the full test suite before every commit: backend `pytest`, `ruff check . ../scripts` and `mypy .` (in `backend/`); frontend `npm run lint`, `npx vitest run`, `npm run build` and `npm run e2e` (in `frontend/`).
   - Pushing `main` to `origin` is allowed, but only after the full suite above has passed. Then confirm CI is green.
   - **Never push `private-history`**, and never commit or push anything in `private/` (it is gitignored: keep it that way).
5. **Dependencies.** Ask before adding any dependency not already in `backend/requirements.txt` or `frontend/package.json`.
