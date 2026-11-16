"""JobStreet module against saved fixtures and a mocked transport. No network."""
import json
from datetime import datetime, timezone

import httpx
import pytest

from models import SearchProfile
from sources.fake import FIXTURES, jobstreet_handler
from sources.http import PoliteClient, RateLimited, SchemaChanged, set_transport_factory
from sources.jobstreet import JobStreetSource, job_id_from_url

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def calls():
    seen: list[httpx.Request] = []
    overrides: dict = {}

    def handler(req):
        seen.append(req)
        return jobstreet_handler(req, overrides)

    set_transport_factory(lambda: httpx.MockTransport(handler))
    yield seen, overrides
    set_transport_factory(None)


def profile(**kw):
    base = dict(name="t", keywords=["software engineer"], locations=["Kuala Lumpur"], job_type="fulltime", days=7)
    base.update(kw)
    return SearchProfile(**base)


def source(**kw):
    return JobStreetSource(PoliteClient(sleep=lambda s: None), now=NOW, **kw)


def test_fetch_normalizes_and_filters(calls):
    seen, _ = calls
    jobs = source().fetch(profile())
    by_id = {j.extra["external_ids"]["jobstreet"]: j for j in jobs}
    assert set(by_id) == {"95667394", "90000001", "90000003"}  # the contract job is not Full time
    insurer = by_id["95667394"]
    assert (insurer.title, insurer.company, insurer.location, insurer.work_arrangement, insurer.job_type) == (
        "Junior Software Engineer", "Contoh Insurans (Malaysia) Berhad", "Kuala Lumpur City Centre, Kuala Lumpur",
        "Hybrid", "Full time")
    assert insurer.url == "https://my.jobstreet.com/job/95667394" and insurer.source == "jobstreet"
    assert insurer.description.startswith("Responsibilities") and "Fresh graduates are encouraged to apply." in insurer.description
    assert str(insurer.posted_date) == "2026-11-04"
    grad = by_id["90000001"]
    assert (grad.salary_min, grad.salary_max, grad.salary_currency) == (3500, 4500, "MYR")
    # 1 search + 3 detail requests; the search asked for the right things
    search = seen[0]
    assert search.url.path == "/api/jobsearch/v5/search"
    params = dict(search.url.params)
    assert {k: params[k] for k in ("siteKey", "keywords", "where", "daterange")} == {
        "siteKey": "MY-Main", "keywords": "software engineer", "where": "Kuala Lumpur", "daterange": "7"}
    assert [r.url.path for r in seen[1:]] == ["/graphql"] * 3


def test_known_jobs_are_not_refetched(calls):
    seen, _ = calls
    jobs = source(known_ids={"95667394", "90000003"}).fetch(profile())
    assert [j.extra["external_ids"]["jobstreet"] for j in jobs] == ["90000001"]
    assert [r.url.path for r in seen] == ["/api/jobsearch/v5/search", "/graphql"]


def test_results_cap_and_remote_location(calls):
    seen, _ = calls
    jobs = source(max_results=2).fetch(profile(locations=["Kuala Lumpur", "Remote"], keywords=["a", "b"]))
    assert len(jobs) == 2
    # Remote is not a JobStreet location; the cap stops further searches
    assert [r.url.path for r in seen].count("/api/jobsearch/v5/search") == 1


def test_detail_failure_keeps_summary(calls):
    _, overrides = calls
    overrides["/graphql"] = httpx.Response(200, json={"errors": [{"message": "unknown field"}]})
    overrides["/job/"] = httpx.Response(200, text="<html><body>blocked</body></html>")
    src = source()
    jobs = src.fetch(profile())
    assert len(jobs) == 3
    assert all("Summary only" in j.description for j in jobs)
    assert any("GraphQL failed" in n for n in src.notes)


def test_rate_limit_stops_and_keeps_partial(calls):
    seen, overrides = calls
    n = {"graphql": 0}

    def second_detail_429():
        n["graphql"] += 1
        detail = json.loads((FIXTURES / "jobstreet_detail_95667394.json").read_text(encoding="utf-8"))
        return httpx.Response(429) if n["graphql"] == 2 else httpx.Response(200, json=detail)

    overrides["/graphql"] = second_detail_429
    src = source()
    with pytest.raises(RateLimited):
        src.fetch(profile())
    assert len(seen) == 3  # search + 2 details, then stop: no retry
    # the job fetched before the 429 is not lost, and the cards already in hand are kept as summaries
    assert len(src.collected) == 3
    assert "Summary only" not in src.collected[0].description
    assert all("Summary only" in j.description for j in src.collected[1:])
    assert any("saved 2 job(s) from their search summary" in n for n in src.notes)


def test_schema_change_is_reported(calls):
    _, overrides = calls
    overrides["/api/jobsearch"] = httpx.Response(200, json={"results": []})
    with pytest.raises(SchemaChanged):
        source().fetch(profile())
    overrides["/api/jobsearch"] = httpx.Response(200, json={"data": [{"foo": 1}]})
    with pytest.raises(SchemaChanged):
        source().fetch(profile())


def test_old_listings_dropped(calls):
    jobs = JobStreetSource(PoliteClient(sleep=lambda s: None), now=datetime(2026, 11, 13, tzinfo=timezone.utc)).fetch(profile(days=7))
    assert {j.extra["external_ids"]["jobstreet"] for j in jobs} == {"90000001", "90000003"}  # 95667394 is 9 days old


@pytest.mark.parametrize("url,expected", [
    ("https://my.jobstreet.com/job/95667394", ("MY", "95667394")),
    ("https://my.jobstreet.com/job/95667394?type=standard&ref=search-standalone#sol=abc", ("MY", "95667394")),
    ("https://my.jobstreet.com/Software-Engineer-jobs/in-Kuala-Lumpur?jobId=95667394&type=standard", ("MY", "95667394")),
    ("https://my.jobstreet.com/companies/x-123/reviews?jobId=95667394", ("MY", "95667394")),
    ("https://sg.jobstreet.com/job/1", None),  # only Malaysia is configured
    ("https://www.linkedin.com/jobs/view/123", None),
])
def test_job_id_from_url(url, expected):
    assert job_id_from_url(url) == expected


# ---------- decision #41: JobStreet URL import goes through this module ----------

def test_url_import_uses_jobstreet_module(client, calls):
    seen, _ = calls
    r = client.post("/api/jobs/fetch-url", json={"url": "https://my.jobstreet.com/job/95667394?ref=x"}).json()
    assert r["ok"] and r["draft"]["company"] == "Contoh Insurans (Malaysia) Berhad"
    assert r["draft"]["work_arrangement"] == "Hybrid" and r["draft"]["external_ids"] == {"jobstreet": "95667394"}
    assert r["draft"]["url"] == "https://my.jobstreet.com/job/95667394"
    assert [q.url.path for q in seen] == ["/graphql"]  # one request
    saved = client.post("/api/jobs/manual", json={k: v for k, v in r["draft"].items() if k not in ("salary_min", "salary_max") or v}).json()
    job = client.get(f"/api/jobs/{saved['id']}").json()["job"]
    assert job["external_ids"] == {"jobstreet": "95667394"} and job["sources"] == ["jobstreet"]
    # importing the same link again: no request, points at the saved job
    again = client.post("/api/jobs/fetch-url", json={"url": "https://my.jobstreet.com/job/95667394"}).json()
    assert not again["ok"] and again["existing_id"] == saved["id"] and len(seen) == 1


def test_url_import_429_pauses_jobstreet(client, calls):
    _, overrides = calls
    overrides["/graphql"] = httpx.Response(429)
    r = client.post("/api/jobs/fetch-url", json={"url": "https://my.jobstreet.com/job/90000001"}).json()
    assert not r["ok"] and "429" in r["error"]
    from sqlmodel import Session

    from app.db import engine
    from models import Source
    with Session(engine) as s:
        assert s.get(Source, "jobstreet").status == "paused"
    r = client.post("/api/jobs/fetch-url", json={"url": "https://my.jobstreet.com/job/90000003"}).json()
    assert not r["ok"] and "paused" in r["error"]


def test_unexpected_response_is_saved_for_debugging(calls):
    from app.config import DATA_DIR
    _, overrides = calls
    overrides["/api/jobsearch"] = httpx.Response(200, json={"results": [{"jobTitle": "x"}]})
    with pytest.raises(SchemaChanged) as e:
        source().fetch(profile())
    saved = str(e.value).split("saved to ")[1]
    assert saved.startswith(str(DATA_DIR / "debug")) and json.loads(open(saved, encoding="utf-8").read()) == {"results": [{"jobTitle": "x"}]}
