"""After smoke test step B (no limit entered, Fetch clicked twice; a "Draughtman" job scored 100):
run log shows the limit and profile used, a running source can't be fetched again, a JD with no
recognised skills gets a low-confidence score capped at 50, a title allow-list rule, tidy Indeed locations.
No network."""
import httpx
import pytest
from sqlmodel import Session, select

from filters.engine import JobView, Rule, check_rule
from filters.service import TITLE_ALLOW_LIST, seed_if_empty
from matcher.rules import location_matches
from models import FilterRule, Job, Notification, SearchProfile
from scheduler.automations import run_automation
from sources import runner
from sources.base import tidy_location
from sources.fake import fake_handler
from sources.http import set_transport_factory
from sources.jobspy_source import _location, fake_scrape

NO_SLEEP = lambda s: None  # noqa: E731
NO_SKILL_JD = ("Job Description:\n- Prepare technical drawings for electrical installations\n"
               "- Coordinate with site supervisors\nRequirements:\n- Diploma or certificate\n- Hardworking and punctual")


def _engine():
    from app.db import engine
    return engine


@pytest.fixture
def fake_net(monkeypatch):
    set_transport_factory(lambda: httpx.MockTransport(fake_handler))
    monkeypatch.setattr("sources.jobspy_source.real_scrape", fake_scrape)
    yield
    set_transport_factory(None)


def _smoke_profile() -> int:
    with Session(_engine()) as s:
        p = SearchProfile(name="Smoke test", keywords=["software engineer"], locations=["Kuala Lumpur"],
                          job_type="fulltime", days=0)
        s.add(p)
        s.commit()
        return p.id


# ---------- run log: the limit and profile actually used ----------

def test_run_log_shows_limit_and_profile(client, fake_net):
    sid = _smoke_profile()
    run_id = run_automation(_engine(), "fetch_jobs", "manual", source_keys=["indeed"], profile_ids=[sid], results_cap=5)
    from models import AutomationRun
    with Session(_engine()) as s:
        assert s.get(AutomationRun, run_id).message.startswith("indeed (limit 5, profile Smoke test): ok:")
    # no limit given -> the source's own limit is shown, so a missing limit is visible afterwards
    run_id = run_automation(_engine(), "fetch_jobs", "manual", source_keys=["indeed"], profile_ids=[sid])
    with Session(_engine()) as s:
        assert s.get(AutomationRun, run_id).message.startswith("indeed (limit 50, profile Smoke test): ok:")


# ---------- a source with a fetch in progress can't be fetched again ----------

def test_running_source_is_refused_and_reported(client, fake_net):
    sid = _smoke_profile()
    assert runner._claim("indeed")  # simulate a fetch in progress
    try:
        assert next(s for s in client.get("/api/sources").json() if s["key"] == "indeed")["running"] is True
        with Session(_engine()) as s:
            [res] = runner.run_fetch(s, source_keys=["indeed"], profile_ids=[sid], sleep=NO_SLEEP)
            assert res.status == "skipped" and "already running" in res.message and res.requests == 0
    finally:
        runner._release("indeed")
    assert next(s for s in client.get("/api/sources").json() if s["key"] == "indeed")["running"] is False
    with Session(_engine()) as s:
        [res] = runner.run_fetch(s, source_keys=["indeed"], profile_ids=[sid], sleep=NO_SLEEP)
        assert res.status == "ok"
    assert runner.running_sources() == set()  # released after the run


# ---------- low confidence: a JD with no recognised skills ----------

def _profile(client):
    p = client.get("/api/profile").json()
    p.update(skills=["Python", "SQL"], years_confirmed=True)
    client.put("/api/profile", json=p)


def test_no_skills_means_low_confidence_capped_at_50(client):
    _profile(client)
    jid = client.post("/api/jobs/manual", json={"title": "Draughtman", "company": "Contoh Elektrik",
                                                "description": NO_SKILL_JD}).json()["id"]
    d = client.get(f"/api/jobs/{jid}").json()
    b = d["match"]["breakdown"]
    assert d["match"]["total"] <= 50
    assert d["low_confidence"].startswith("Not enough information to assess skills")
    req = next(c for c in b["categories"] if c["key"] == "required_skills")
    assert req["points"] == 0 and req["note"] == "Not enough information to assess skills"
    assert next(j for j in client.get("/api/jobs").json() if j["id"] == jid)["low_confidence"]


def test_jd_with_skills_is_unaffected(client):
    _profile(client)
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "company": "C",
                                                "description": "Requirements:\n- Python\n- SQL\n- Fresh graduates welcome"}).json()["id"]
    d = client.get(f"/api/jobs/{jid}").json()
    assert d["low_confidence"] == "" and d["match"]["total"] > 50


def test_high_match_alert_skips_low_confidence(client):
    _profile(client)
    low = client.post("/api/jobs/manual", json={"title": "Draughtman", "description": NO_SKILL_JD}).json()["id"]
    assert client.get(f"/api/jobs/{low}").json()["match"]["total"] >= 30  # above the threshold set below
    client.post("/api/jobs/manual", json={"title": "Dev", "description": "Requirements:\n- Python\n- SQL\n- Fresh graduates welcome"})
    settings = client.get("/api/settings").json()
    settings["general"]["high_match_threshold"] = 30
    client.put("/api/settings", json=settings)
    run_automation(_engine(), "high_match_alert")
    with Session(_engine()) as s:
        notes = s.exec(select(Notification).where(Notification.type == "high_match")).all()
        assert [n.message.split(": ", 1)[1] for n in notes] == ["Dev"]  # the low-confidence job is not alerted


# ---------- title allow-list rule ----------

ALLOW = Rule(None, "title_must_contain_one_of", TITLE_ALLOW_LIST)


@pytest.mark.parametrize("title,hidden", [
    ("Draughtman", True),
    ("Production Technologist", True),
    ("Associate - Bridges and Structures", True),
    ("Junior Software Engineer", False),
    ("Software Tester", False),  # "test" starts a word
    ("IT Support Engineer- Malaysia", False),
    ("Java Developer", False),
    ("Full Stack Engineer", False),
    ("Data Analyst", False),
    ("Item Coordinator", True),  # "IT" must be a whole word
    ("Quality Assurance (QA) Executive", False),
])
def test_title_allow_list(title, hidden):
    reason = check_rule(ALLOW, JobView(title, "", ""))
    assert (reason is not None) == hidden
    if hidden:
        assert reason.startswith("Title has none of: software, developer")


def test_allow_list_seeded_disabled_also_into_existing_databases(client):
    with Session(_engine()) as s:
        rule = s.exec(select(FilterRule).where(FilterRule.type == "title_must_contain_one_of")).one()
        assert rule.enabled is False and rule.value == TITLE_ALLOW_LIST
        s.delete(rule)  # an older database without it
        s.commit()
        seed_if_empty(s)
        seed_if_empty(s)  # idempotent
        assert len(s.exec(select(FilterRule).where(FilterRule.type == "title_must_contain_one_of")).all()) == 1


def test_allow_list_hides_with_reason_when_turned_on(client):
    rule = next(r for r in client.get("/api/filters").json() if r["type"] == "title_must_contain_one_of")
    jid = client.post("/api/jobs/manual", json={"title": "Draughtman", "description": NO_SKILL_JD}).json()["id"]
    client.put(f"/api/filters/{rule['id']}", json={**rule, "enabled": True})
    job = next(j for j in client.get("/api/jobs").json() if j["id"] == jid)
    assert job["hidden"] and job["hidden_reason"].startswith("Title has none of:")


# ---------- Indeed locations ----------

@pytest.mark.parametrize("raw,tidy", [
    ("Kuala Lumpur, M14, Malaysia", "Kuala Lumpur"),
    ("Bangsar South, M14, Malaysia", "Bangsar South"),
    ("Petaling Jaya, Selangor", "Petaling Jaya, Selangor"),
    ("Malaysia", "Malaysia"),
    ("", ""),
])
def test_tidy_location(raw, tidy):
    assert tidy_location(raw) == tidy


def test_jobspy_location_and_matching_use_tidy_text():
    assert _location({"city": "Kuala Lumpur", "state": "M14", "country": "MALAYSIA"}) == "Kuala Lumpur"
    assert location_matches("Kuala Lumpur, M14, Malaysia", ["Kuala Lumpur"]) == ("Kuala Lumpur", "Kuala Lumpur")


def test_stored_locations_tidied_once_at_startup(client):
    from sources.ingest import tidy_stored_locations
    with Session(_engine()) as s:
        s.add(Job(title="QA Engineer", company="Contoh Capital", location="Kuala Lumpur, M14, Malaysia", dedupe_key="x"))
        s.commit()
        assert tidy_stored_locations(s) == 1 and tidy_stored_locations(s) == 0
        job = s.exec(select(Job)).one()
        assert job.location == "Kuala Lumpur" and job.dedupe_key.endswith("|kuala lumpur")
