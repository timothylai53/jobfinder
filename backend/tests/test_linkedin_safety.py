"""LinkedIn descriptions are fetched by us (paced, blocks detected); JobSpy's silent throttling is caught.
All mocked: fake transport + fake JobSpy. No network."""
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pandas as pd
import pytest
from sqlmodel import Session, select

from models import Job, Notification, SearchProfile, Source
from sources.fake import fake_handler
from sources.http import RateLimited, set_transport_factory
from sources.jobspy_source import JobSpySource, fake_scrape, run_scrape

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
NO_SLEEP = lambda s: None  # noqa: E731


def prof(**kw):
    base = dict(name="t", keywords=["software engineer"], locations=["Kuala Lumpur"], job_type="fulltime", days=7)
    base.update(kw)
    return SearchProfile(**base)


@pytest.fixture
def net(monkeypatch):
    seen: list[httpx.Request] = []
    overrides: dict = {}

    def handler(r):
        seen.append(r)
        return fake_handler(r, overrides)

    set_transport_factory(lambda: httpx.MockTransport(handler))
    monkeypatch.setattr("sources.jobspy_source.real_scrape", fake_scrape)
    yield seen, overrides
    set_transport_factory(None)


# ---------- descriptions through PoliteClient ----------

def test_linkedin_descriptions_fetched_by_us_and_paced(net):
    seen, _ = net
    calls, pauses = [], []

    def scrape(**kw):
        calls.append(kw)
        return fake_scrape(**kw)

    jobs = JobSpySource("linkedin", scrape=scrape, sleep=pauses.append).fetch(prof())
    assert calls[0]["fetch_description"] is False  # JobSpy only reads search pages
    assert [r.url.path for r in seen] == ["/jobs/view/4012345678", "/jobs/view/4012345679", "/jobs/view/4012345680"]
    assert all(r.headers["user-agent"].startswith("Mozilla/5.0") and "JobFinder" in r.headers["user-agent"] for r in seen)
    assert len(pauses) == 3 and all(2 <= p <= 6 for p in pauses)  # incl. a pause before the first job page
    fresh = next(j for j in jobs if j.title == "Software Engineer (Fresh Graduate)")
    assert fresh.description.startswith("Requirements") and "Fresh graduates are welcome" in fresh.description


def test_known_linkedin_jobs_get_no_page_request(net):
    seen, _ = net
    JobSpySource("linkedin", scrape=fake_scrape, sleep=NO_SLEEP,
                 known={"li-4012345678", "li-4012345679"}).fetch(prof())
    assert [r.url.path for r in seen] == ["/jobs/view/4012345680"]


def test_cap_limits_page_requests(net):
    seen, _ = net
    jobs = JobSpySource("linkedin", max_results=1, scrape=fake_scrape, sleep=NO_SLEEP).fetch(prof())
    assert len(jobs) == 1 and len(seen) == 1


@pytest.mark.parametrize("response", [
    httpx.Response(429), httpx.Response(403), httpx.Response(999),
])
def test_block_on_a_job_page_raises_and_keeps_earlier_jobs(net, response):
    seen, overrides = net
    count = {"n": 0}

    def second_blocked():
        count["n"] += 1
        return response if count["n"] == 2 else fake_handler(seen[-1])

    overrides["/jobs/view/"] = second_blocked
    src = JobSpySource("linkedin", scrape=fake_scrape, sleep=NO_SLEEP)
    with pytest.raises(RateLimited):
        src.fetch(prof())
    assert len(seen) == 2  # stopped at once, nothing retried
    # the job before the block keeps its description; the rest of the search results are kept as summaries
    assert len(src.collected) == 3 and "Summary only" not in src.collected[0].description
    assert all("Summary only" in j.description for j in src.collected[1:])


def test_redirect_to_authwall_is_a_block(net):
    _, overrides = net
    overrides["/jobs/view/"] = httpx.Response(302, headers={"Location": "https://www.linkedin.com/authwall?trk=x"})
    overrides["/authwall"] = httpx.Response(200, text="<html>Sign in</html>")
    with pytest.raises(RateLimited):
        JobSpySource("linkedin", scrape=fake_scrape, sleep=NO_SLEEP).fetch(prof())


def test_page_without_description_block_is_kept_as_summary(net):
    _, overrides = net
    overrides["/jobs/view/"] = httpx.Response(200, text="<html><body>new layout</body></html>")
    src = JobSpySource("linkedin", scrape=fake_scrape, sleep=NO_SLEEP)
    jobs = src.fetch(prof())
    assert len(jobs) == 3 and all("Summary only" in j.description for j in jobs)
    assert any("no description block" in n for n in src.notes)


# ---------- the runner: a 429 on a LinkedIn job page pauses LinkedIn for 24 h ----------

def test_runner_pauses_linkedin_on_job_page_429(client, net):
    seen, overrides = net
    overrides["/jobs/view/4012345679"] = httpx.Response(429)
    from app.db import engine
    from sources.runner import run_fetch
    with Session(engine) as s:
        for p in s.exec(select(SearchProfile)).all():
            p.enabled, p.keywords, p.locations = p.name == "KL/Selangor", ["software engineer"], ["Kuala Lumpur"]
        s.commit()
        res = {r.key: r for r in run_fetch(s, source_keys=["linkedin"], now=NOW, sleep=NO_SLEEP)}
        li = res["linkedin"]
        assert li.status == "paused" and "429" in li.message
        assert li.fetched == 3 and li.requests == 1 + 2  # 1 JobSpy search + 2 job pages (the 2nd answered 429)
        assert "job pages blocked: saved 2 job(s)" in li.message  # the source's notes reach the run log
        src = s.get(Source, "linkedin")
        assert src.status == "paused" and src.paused_until.replace(tzinfo=UTC) == NOW + timedelta(hours=24)
        assert any("LinkedIn paused for 24 hours" in n.message for n in s.exec(select(Notification)).all())
        jobs = s.exec(select(Job)).all()
        assert len(jobs) == 3 and jobs[0].title == "Junior Software Engineer"  # the job before the 429 is kept
        assert "Summary only" not in jobs[0].description and all("Summary only" in j.description for j in jobs[1:])


# ---------- safety net for JobSpy's silent throttling ----------

def _rows(n, description="x"):
    return [{"id": f"in-{i}", "title": f"Dev {i}", "company": "c", "job_url": f"https://my.indeed.com/viewjob?jk={i}",
             "description": description} for i in range(n)]


@pytest.mark.parametrize("warning", [
    "job 123: response status code 429 (blocked: use a proxy)",
    "empty page at start=25 (the end of the results, or throttled)",
    "job 1: redirected to /authwall",
])
def test_throttling_warning_is_rate_limited(warning):
    src = JobSpySource("indeed", scrape=lambda **kw: (_rows(2), "", [warning]), sleep=NO_SLEEP)
    with pytest.raises(RateLimited):
        src.fetch(prof())


def test_end_of_results_warning_with_enough_rows_is_fine():
    w = "empty page at start=25 (the end of the results, or throttled)"
    src = JobSpySource("indeed", max_results=3, scrape=lambda **kw: (_rows(3), "", [w]), sleep=NO_SLEEP)
    assert len(src.fetch(prof())) == 3
    assert any(w in n for n in src.notes)  # still visible in the run log


def test_mostly_empty_descriptions_is_rate_limited():
    src = JobSpySource("indeed", scrape=lambda **kw: (_rows(4, description=None), "", []), sleep=NO_SLEEP)
    with pytest.raises(RateLimited):
        src.fetch(prof())
    ok = JobSpySource("indeed", scrape=lambda **kw: (_rows(2, description=None), "", []), sleep=NO_SLEEP)
    assert len(ok.fetch(prof())) == 2  # too few rows to judge


def test_harmless_warnings_reach_the_run_log():
    src = JobSpySource("indeed", scrape=lambda **kw: (_rows(2), "", ["is_remote isn't supported, ignoring it"]), sleep=NO_SLEEP)
    src.fetch(prof())
    assert src.notes == ["JobSpy warning: is_remote isn't supported, ignoring it"]


def test_run_scrape_collects_returned_and_logged_warnings():
    """JobSpy reports some warnings in df.attrs and only LOGS others (a 429 on a job page): both are read."""
    def fake_scrape_jobs(**kw):
        assert kw["verbose"] == 1  # warnings must be emitted, not filtered out
        logging.getLogger("jobspy.linkedin").warning("job 42: response status code 429 (blocked: use a proxy)")
        df = pd.DataFrame(_rows(1))
        df.attrs = {"errors": {}, "warnings": {"linkedin": ["is_remote isn't supported, ignoring it"]}}
        return df

    rows, error, warnings = run_scrape(fake_scrape_jobs, site_name=["linkedin"], verbose=0)
    assert len(rows) == 1 and error == ""
    assert warnings == ["is_remote isn't supported, ignoring it", "job 42: response status code 429 (blocked: use a proxy)"]
    assert not any(isinstance(h, logging.Handler) and h.__class__.__name__ == "_Capture"
                   for h in logging.getLogger("jobspy").handlers)  # capture handler removed again
