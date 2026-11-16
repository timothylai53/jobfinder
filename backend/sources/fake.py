"""Fake sources that replay saved fixtures: used by tests and by JOBFINDER_FAKE_SOURCES=1 (browser checks).

No network at all. Fixtures live in backend/tests/fixtures/sources/.
"""
import json
from pathlib import Path

import httpx

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sources"


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def jobstreet_handler(request: httpx.Request, overrides: dict | None = None) -> httpx.Response:
    """Replays JobStreet: search returns the saved cards on page 1 only; details per job id."""
    overrides = overrides or {}
    path = request.url.path
    for prefix, resp in overrides.items():  # tests: force 429/403/500 on a path
        if path.startswith(prefix):
            return resp() if callable(resp) else resp
    if path == "/api/jobsearch/v5/search":
        page = int(request.url.params.get("page", "1"))
        data = _load("jobstreet_search.json")
        return httpx.Response(200, json=data if page == 1 else {**data, "data": []})
    if path == "/graphql":
        job_id = json.loads(request.content)["variables"]["jobId"]
        f = FIXTURES / f"jobstreet_detail_{job_id}.json"
        return httpx.Response(200, json=_load(f.name)) if f.exists() else httpx.Response(200, json={"data": {"jobDetails": None}})
    if path.startswith("/job/"):
        return httpx.Response(404)
    return httpx.Response(404)


def linkedin_handler(request: httpx.Request, overrides: dict | None = None) -> httpx.Response:
    """Replays LinkedIn's public job pages (/jobs/view/<id>)."""
    for prefix, resp in (overrides or {}).items():
        if request.url.path.startswith(prefix):
            return resp() if callable(resp) else resp
    job_id = request.url.path.rstrip("/").rsplit("/", 1)[-1]
    f = FIXTURES / f"linkedin_job_{job_id}.html"
    return httpx.Response(200, text=f.read_text(encoding="utf-8")) if f.exists() else httpx.Response(404)


def fake_handler(request: httpx.Request, overrides: dict | None = None) -> httpx.Response:
    if "linkedin.com" in request.url.host:
        return linkedin_handler(request, overrides)
    return jobstreet_handler(request, overrides)


def fake_transport() -> httpx.BaseTransport:
    return httpx.MockTransport(fake_handler)


def jobspy_rows(site: str) -> list[dict]:
    """Saved JobSpy-shaped rows per site (fake companies)."""
    return _load("jobspy_rows.json").get(site, [])
