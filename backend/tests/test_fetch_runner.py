"""JobSpy source + the fetch runner, end to end against fixtures. No network: JobSpy's scrape function and
the HTTP transport are both replaced."""
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlmodel import Session, select

from models import Job, Notification, SearchProfile, Source
from sources.fake import fake_handler
from sources.http import RateLimited, SourceError, set_transport_factory
from sources.jobspy_source import JobSpySource, fake_scrape

NOW = datetime(2026, 11, 8, 9, 0, tzinfo=UTC)
NO_SLEEP = lambda s: None  # noqa: E731


def prof(**kw):
    base = dict(name="t", keywords=["software engineer"], locations=["Kuala Lumpur"], job_type="fulltime", days=7)
    base.update(kw)
    return SearchProfile(**base)


# ---------- JobSpy source on its own ----------

def test_jobspy_rows_normalized(fake_net):
    src = JobSpySource("indeed", scrape=fake_scrape, sleep=NO_SLEEP)
    jobs = {j.title: j for j in src.fetch(prof())}
    grad = jobs["Graduate Software Engineer"]
    assert (grad.company, grad.location, grad.salary_min, grad.salary_max, grad.salary_currency) == (
        "Contoh Teknologi Sdn Bhd", "Petaling Jaya, Selangor", 3500, 4500, "MYR")
    assert grad.extra["external_ids"] == {"indeed": "in-abc123"} and grad.source == "indeed"
    assert grad.job_type == "Full time" and str(grad.posted_date) == "2026-11-06"
    remote = jobs["Remote Junior Developer"]
    assert remote.work_arrangement == "Remote" and remote.salary_min is None  # hourly pay is not a monthly salary
    yearly = {j.title: j for j in JobSpySource("linkedin", scrape=fake_scrape, sleep=NO_SLEEP).fetch(prof())}
    assert (yearly["Software Engineer (Fresh Graduate)"].salary_min, yearly["Software Engineer (Fresh Graduate)"].salary_max) == (4000, 5000)


def test_jobspy_call_arguments_and_cap(fake_net):
    calls = []

    def scrape(**kw):
        calls.append(kw)
        return fake_scrape(**kw)

    pauses = []
    src = JobSpySource("linkedin", max_results=2, scrape=scrape, sleep=pauses.append)
    jobs = src.fetch(prof(keywords=["a", "b"], locations=["Kuala Lumpur", "Remote"]))
    assert len(jobs) == 2 and len(calls) == 1  # cap reached on the first call: no more requests
    kw = calls[0]
    assert kw["site_name"] == ["linkedin"] and kw["location"] == "Kuala Lumpur, Malaysia"
    assert (kw["country_indeed"], kw["hours_old"], kw["job_type"], kw["results_wanted"]) == ("malaysia", 168, "fulltime", 2)
    assert kw["fetch_description"] is False and "user_agent" not in kw  # we fetch LinkedIn pages ourselves (#92)
    calls.clear()
    JobSpySource("indeed", max_results=50, scrape=scrape, sleep=pauses.append).fetch(prof(locations=["Selangor", "Remote"]))
    assert [c["location"] for c in calls] == ["Selangor, Malaysia", "Malaysia"] and calls[1]["is_remote"] is True
    assert calls[0]["fetch_description"] is False
    assert pauses and all(2 <= p <= 6 for p in pauses)


@pytest.mark.parametrize("error,exc", [
    ("Error: 429 Too Many Requests", RateLimited),
    ("blocked by anti-bot (403 Forbidden)", RateLimited),
    ("unexpected response: 500", SourceError),
])
def test_jobspy_errors_classified(error, exc):
    src = JobSpySource("linkedin", scrape=lambda **kw: ([], error, []), sleep=NO_SLEEP)
    with pytest.raises(exc):
        src.fetch(prof())


def test_glassdoor_thin_coverage_is_a_note_not_a_failure():
    src = JobSpySource("glassdoor", scrape=lambda **kw: ([], "Glassdoor: location not supported for Malaysia", []), sleep=NO_SLEEP)
    assert src.fetch(prof()) == [] and "Malaysia coverage" in src.notes[0]
    src = JobSpySource("glassdoor", scrape=fake_scrape, sleep=NO_SLEEP)  # zero rows
    assert src.fetch(prof()) == [] and "no jobs" in src.notes[0]

    def raises(**kw):
        raise ValueError("Glassdoor is not available for Malaysia")
    src = JobSpySource("glassdoor", scrape=raises, sleep=NO_SLEEP)
    assert src.fetch(prof()) == [] and "Malaysia coverage" in src.notes[0]


def test_known_jobs_skipped():
    src = JobSpySource("indeed", scrape=fake_scrape, known={"in-abc123", "https://my.indeed.com/viewjob?jk=def456"}, sleep=NO_SLEEP)
    assert [j.title for j in src.fetch(prof())] == ["Remote Junior Developer"]


# ---------- the runner: all sources, the shared pipeline, safety ----------

@pytest.fixture
def fake_net(monkeypatch):
    overrides: dict = {}
    set_transport_factory(lambda: httpx.MockTransport(lambda r: fake_handler(r, overrides)))
    monkeypatch.setattr("sources.jobspy_source.real_scrape", fake_scrape)
    yield overrides
    set_transport_factory(None)


def _setup(client, *, glassdoor=False):
    """One profile (KL), clean slate of jobs."""
    from app.db import engine
    with Session(engine) as s:
        for p in s.exec(select(SearchProfile)).all():
            p.enabled = p.name == "KL/Selangor"
            p.locations = ["Kuala Lumpur"]
            p.keywords = ["software engineer"]
        s.get(Source, "glassdoor").enabled = glassdoor
        s.commit()


def run(**kw):
    from app.db import engine
    from sources.runner import run_fetch
    with Session(engine) as s:
        return {r.key: r for r in run_fetch(s, now=kw.pop("now", NOW), sleep=NO_SLEEP, **kw)}


def test_fetch_all_sources_through_shared_pipeline(client, fake_net):
    _setup(client, glassdoor=True)
    res = run()
    assert [k for k in res] == ["jobstreet", "linkedin", "indeed", "glassdoor"]
    assert res["jobstreet"].new == 3 and res["jobstreet"].requests == 4  # 1 search + 3 details
    # cross-source duplicates merge into one job with several sources and links
    assert res["linkedin"].merged == 1 and res["indeed"].merged == 1
    assert res["glassdoor"].status == "ok" and "Malaysia coverage" in res["glassdoor"].message
    from app.db import engine
    with Session(engine) as s:
        jobs = {j.title: j for j in s.exec(select(Job)).all()}
        insurer = jobs["Junior Software Engineer"]
        assert sorted(insurer.sources) == ["jobstreet", "linkedin"] and len(insurer.urls) == 2
        assert insurer.external_ids == {"jobstreet": "95667394", "linkedin": "li-4012345678"}
        assert insurer.description.startswith("Responsibilities")  # the full JobStreet JD, not LinkedIn's short copy
        grad = jobs["Graduate Software Engineer"]
        assert sorted(grad.sources) == ["indeed", "jobstreet"]
        # filters + score from the Phase 1 pipeline
        assert jobs["Senior Software Engineer"].hidden and "Senior" in jobs["Senior Software Engineer"].hidden_reason
        assert jobs["Lead Backend Engineer"].hidden
        from models import MatchResult
        assert len(s.exec(select(MatchResult)).all()) == len(jobs)


def test_second_run_refetches_nothing_and_daily_limit(client, fake_net):
    _setup(client)
    run()
    res = run(now=NOW + timedelta(hours=1))
    assert res["jobstreet"].new == 0 and res["jobstreet"].requests == 1  # search only: details are cached
    assert res["linkedin"].status == "skipped" and "daily limit" in res["linkedin"].message  # 1 run/day
    res = run(now=NOW + timedelta(hours=2))
    assert res["jobstreet"].status == "skipped"  # 2 runs/day used up


def test_rate_limit_pauses_one_source_others_continue(client, fake_net):
    _setup(client)
    fake_net["/api/jobsearch"] = httpx.Response(429)
    res = run()
    assert res["jobstreet"].status == "paused" and "429" in res["jobstreet"].message
    assert res["indeed"].status == "ok" and res["indeed"].new == 3
    from app.db import engine
    with Session(engine) as s:
        js = s.get(Source, "jobstreet")
        assert js.status == "paused" and js.paused_until.replace(tzinfo=UTC) == NOW + timedelta(hours=24)
        assert any("JobStreet paused" in n.message for n in s.exec(select(Notification)).all())
    fake_net.clear()
    res = run(now=NOW + timedelta(hours=3))
    assert res["jobstreet"].status == "skipped" and "paused until" in res["jobstreet"].message


def test_three_errors_in_a_row_pause(client, fake_net):
    _setup(client)
    fake_net["/api/jobsearch"] = httpx.Response(500)
    from app.db import engine
    for i in range(3):
        with Session(engine) as s:  # reset the daily counter so three runs can happen
            src = s.get(Source, "jobstreet")
            src.runs_today = 0
            s.commit()
        res = run(source_keys=["jobstreet"], now=NOW + timedelta(minutes=i))
    assert res["jobstreet"].status == "paused" and "3 errors in a row" in res["jobstreet"].message


def test_results_cap_override_for_smoke_test(client, fake_net):
    _setup(client)
    res = run(source_keys=["indeed"], results_cap=2)
    assert res["indeed"].fetched == 2 and set(res) == {"indeed"}


def test_two_profiles_do_not_refetch_the_same_jobs(client, fake_net):
    from app.db import engine
    with Session(engine) as s:
        for p in s.exec(select(SearchProfile)).all():
            p.enabled, p.keywords = True, ["software engineer"]
            p.locations = ["Kuala Lumpur"] if p.name == "KL/Selangor" else ["Sabah"]
        s.commit()
    res = run(source_keys=["jobstreet", "indeed"])
    assert res["jobstreet"].fetched == 3 and res["jobstreet"].requests == 2 + 3  # 2 searches + 3 details, once
    assert res["indeed"].fetched == 3 and res["indeed"].merged == 1  # only the cross-site twin of a JobStreet job


def test_single_profile_smoke_run_makes_minimal_requests(client, fake_net):
    """The smoke-test shape: one source, one one-keyword profile, cap 5 -> 1 search + details only."""
    from app.db import engine
    with Session(engine) as s:
        smoke = SearchProfile(name="Smoke test", keywords=["software engineer"], locations=["Kuala Lumpur"],
                              job_type="fulltime", days=7)
        s.add(smoke)
        s.commit()
        sid = smoke.id
    res = run(source_keys=["jobstreet"], profile_ids=[sid], results_cap=5)
    assert set(res) == {"jobstreet"} and res["jobstreet"].requests == 1 + 3  # 3 full-time cards in the fixture
