"""Automations, scheduler catch-up, the Phase 2 APIs and Skill Gaps. No network (fake sources)."""
import time
from datetime import UTC, date, datetime, timedelta, timezone

import httpx
import pytest
from sqlmodel import Session, select

from models import Application, Automation, AutomationRun, Job, Notification, SearchProfile, Source
from scheduler.automations import SPECS, merge_duplicates, run_automation
from scheduler.service import last_due, missed
from sources.fake import fake_handler
from sources.http import set_transport_factory
from sources.jobspy_source import fake_scrape

MYT = timezone(timedelta(hours=8))


@pytest.fixture
def engine():
    from app.db import engine
    return engine


@pytest.fixture
def fake_net(monkeypatch):
    set_transport_factory(lambda: httpx.MockTransport(fake_handler))
    monkeypatch.setattr("sources.jobspy_source.real_scrape", fake_scrape)
    monkeypatch.setattr("sources.http.DEFAULT_DELAY", (0, 0))
    yield
    set_transport_factory(None)


def _one_profile(engine):
    with Session(engine) as s:
        for p in s.exec(select(SearchProfile)).all():
            p.enabled = p.name == "KL/Selangor"
            p.locations, p.keywords = ["Kuala Lumpur"], ["software engineer"]
            p.days = 0  # these runs use today's clock: don't let the fixtures' listing dates age out
        s.commit()


# ---------- defaults ----------

def test_defaults(client, engine):
    with Session(engine) as s:
        autos = {a.key: a for a in s.exec(select(Automation)).all()}
    assert set(autos) == set(SPECS)
    assert autos["fetch_jobs"].enabled is False and autos["fetch_jobs"].schedule == "09:00"  # OFF until I turn it on
    assert autos["follow_up_reminder"].enabled and autos["follow_up_reminder"].schedule == "09:00"
    assert autos["score_new_jobs"].schedule == "after:fetch_jobs"
    oda = autos["ollama_deep_analysis"]  # Phase 3: OFF by default (brief §6.10)
    assert oda.enabled is False and oda.schedule == "after:fetch_jobs"


# ---------- catch-up ----------

@pytest.mark.parametrize("now,expected", [
    (datetime(2026, 11, 8, 10, 0, tzinfo=MYT), datetime(2026, 11, 8, 9, 0, tzinfo=MYT)),
    (datetime(2026, 11, 8, 8, 0, tzinfo=MYT), datetime(2026, 11, 7, 9, 0, tzinfo=MYT)),
])
def test_last_due(now, expected):
    assert last_due("09:00", now) == expected


def test_missed_rules():
    now = datetime(2026, 11, 8, 10, 0, tzinfo=MYT)
    a = Automation(key="follow_up_reminder", enabled=True, mode="scheduled", schedule="09:00")
    assert missed(a, now)  # never ran
    a.last_run_at = datetime(2026, 11, 8, 9, 0, 5, tzinfo=MYT)
    assert not missed(a, now)  # ran today after 09:00
    a.last_run_at = datetime(2026, 11, 7, 9, 0, 5, tzinfo=MYT)
    assert missed(a, now)  # yesterday's run: today's 09:00 was missed
    assert not missed(a, datetime(2026, 11, 8, 8, 0, tzinfo=MYT))  # today's run is not due yet
    a.enabled = False
    assert not missed(a, now)
    off = Automation(key="fetch_jobs", enabled=False, mode="scheduled", schedule="09:00")
    assert not missed(off, now)  # fetch is off by default: no catch-up fetch
    chained = Automation(key="score_new_jobs", enabled=True, mode="scheduled", schedule="after:fetch_jobs")
    assert not missed(chained, now)
    manual = Automation(key="follow_up_reminder", enabled=True, mode="manual", schedule="09:00")
    assert not missed(manual, now)


def test_catch_up_runs_missed_once(client, engine):
    from scheduler.service import AutomationScheduler
    sched = AutomationScheduler(engine)
    first = sched.catch_up()
    assert first == ["follow_up_reminder"]  # enabled + daily + never ran; fetch_jobs is off
    assert sched.catch_up() == []  # not twice
    with Session(engine) as s:
        runs = s.exec(select(AutomationRun).where(AutomationRun.trigger == "catch-up")).all()
        assert [r.automation_key for r in runs] == ["follow_up_reminder"]


def test_scheduler_registers_daily_jobs(client, engine):
    from scheduler.service import AutomationScheduler
    sched = AutomationScheduler(engine)
    sched.sched.start(paused=True)
    try:
        sched.reschedule()
        assert {j.id for j in sched.sched.get_jobs()} == {"follow_up_reminder"}  # fetch_jobs off
        with Session(engine) as s:
            s.get(Automation, "fetch_jobs").enabled = True
            s.commit()
        sched.reschedule()
        assert {j.id for j in sched.sched.get_jobs()} == {"follow_up_reminder", "fetch_jobs"}
    finally:
        sched.sched.shutdown(wait=False)


# ---------- runs ----------

def test_fetch_run_logs_and_chains(client, engine, fake_net):
    _one_profile(engine)
    run_id = run_automation(engine, "fetch_jobs", "manual", source_keys=["jobstreet", "indeed"])
    with Session(engine) as s:
        run = s.get(AutomationRun, run_id)
        assert run.result == "ok" and run.items_processed == 5 and "jobstreet (limit 50, profile KL/Selangor): ok" in run.message
        chained = [r.automation_key for r in s.exec(select(AutomationRun).where(AutomationRun.trigger == "chain")).all()]
        assert chained == ["dedupe_and_filter", "score_new_jobs", "high_match_alert"]
        assert s.get(Automation, "fetch_jobs").last_run_at is not None


def test_failing_task_is_logged_not_raised(client, engine, monkeypatch):
    def boom(session, **_):
        raise RuntimeError("kaput")
    monkeypatch.setitem(__import__("scheduler.automations", fromlist=["TASKS"]).TASKS, "score_new_jobs", boom)
    run_id = run_automation(engine, "score_new_jobs")
    with Session(engine) as s:
        run = s.get(AutomationRun, run_id)
        assert run.result == "error" and "kaput" in run.error and run.finished_at


def test_high_match_alert_once_per_job(client, engine):
    profile = client.get("/api/profile").json()
    profile.update(skills=["Python", "SQL"], years_confirmed=True)
    client.put("/api/profile", json=profile)
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "company": "Contoh",
                                                "description": "Requirements:\n- Python\n- SQL\n- Fresh graduates welcome"}).json()["id"]
    run_automation(engine, "high_match_alert")
    run_automation(engine, "high_match_alert")
    with Session(engine) as s:
        notes = [n for n in s.exec(select(Notification).where(Notification.type == "high_match")).all()]
        assert len(notes) == 1 and notes[0].link == f"/jobs/{jid}" and "Dev at Contoh" in notes[0].message


def test_follow_up_reminder_once_per_due_date(client, engine):
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "description": "x"}).json()["id"]
    app_id = client.post("/api/applications", json={"job_id": jid}).json()["id"]
    past = (date.today() - timedelta(days=1)).isoformat()
    client.patch(f"/api/applications/{app_id}", json={"status": "Applied", "applied_at": past, "follow_up_at": past})
    run_automation(engine, "follow_up_reminder")
    run_automation(engine, "follow_up_reminder")
    with Session(engine) as s:
        assert len(s.exec(select(Notification).where(Notification.type == "follow_up")).all()) == 1
    # moving the follow-up date later and passing it again reminds again
    client.patch(f"/api/applications/{app_id}", json={"follow_up_at": date.today().isoformat()})
    run_automation(engine, "follow_up_reminder")
    with Session(engine) as s:
        assert len(s.exec(select(Notification).where(Notification.type == "follow_up")).all()) == 2


def test_merge_duplicates_keeps_tracker_entry(client, engine):
    with Session(engine) as s:
        a = Job(title="Dev", company="Contoh", location="Kuala Lumpur City Centre, Kuala Lumpur", dedupe_key="contoh|dev|kuala lumpur city centre",
                urls=["https://my.jobstreet.com/job/1"], sources=["jobstreet"], external_ids={"jobstreet": "1"}, description="full")
        b = Job(title="Dev", company="Contoh", location="Kuala Lumpur", dedupe_key="contoh|dev|kuala lumpur",
                urls=["https://www.linkedin.com/jobs/view/2"], sources=["linkedin"], external_ids={"linkedin": "2"}, description="x")
        s.add(a)
        s.add(b)
        s.commit()
        s.add(Application(job_id=b.id))
        s.commit()
        assert merge_duplicates(s) == 1
        left = s.exec(select(Job)).all()
        assert len(left) == 1 and sorted(left[0].sources) == ["jobstreet", "linkedin"]
        assert left[0].external_ids == {"jobstreet": "1", "linkedin": "2"}
        assert s.exec(select(Application)).one().job_id == left[0].id


# ---------- APIs ----------

def test_sources_api(client):
    rows = {r["key"]: r for r in client.get("/api/sources").json()}
    assert list(rows) == ["jobstreet", "linkedin", "indeed", "glassdoor"]
    assert rows["glassdoor"]["enabled"] is False and rows["linkedin"]["max_results"] == 15
    r = client.put("/api/sources/linkedin", json={"enabled": True, "max_results": 999, "max_runs_per_day": 9}).json()
    assert (r["max_results"], r["max_runs_per_day"]) == (30, 2)  # safe maximums
    from app.db import engine
    with Session(engine) as s:
        src = s.get(Source, "indeed")
        src.status, src.paused_until, src.last_error = "paused", datetime.now(UTC) + timedelta(hours=5), "x"
        s.commit()
    assert {r["key"]: r for r in client.get("/api/sources").json()}["indeed"]["status"] == "paused"
    assert client.post("/api/sources/indeed/resume").json()["status"] == "ok"
    dash = {d["key"]: d for d in client.get("/api/dashboard").json()["sources"]}
    assert dash["glassdoor"]["status"] == "disabled" and dash["jobstreet"]["note"] == "not run yet"


def test_search_profiles_api(client):
    profiles = client.get("/api/search-profiles").json()
    assert [p["name"] for p in profiles] == ["KL/Selangor", "Sabah"]
    new = client.post("/api/search-profiles", json={"name": " Penang ", "keywords": ["qa engineer", " "],
                                                    "locations": ["Penang"], "sources": ["jobstreet", "bogus"], "days": 99}).json()
    assert (new["name"], new["keywords"], new["sources"], new["days"]) == ("Penang", ["qa engineer"], ["jobstreet"], 31)
    assert client.post("/api/search-profiles", json={"name": "x", "keywords": []}).status_code == 422
    assert client.delete(f"/api/search-profiles/{new['id']}").status_code == 200


def test_fetch_now_api_runs_in_background(client, engine, fake_net):
    _one_profile(engine)
    run_id = client.post("/api/fetch", json={"source_keys": ["indeed"], "results_cap": 2}).json()["run_id"]
    for _ in range(100):
        run = client.get(f"/api/automations/runs/{run_id}").json()
        if run["result"] != "running":
            break
        time.sleep(0.05)
    assert run["result"] == "ok" and run["items_processed"] == 2 and "indeed (limit 2, profile KL/Selangor): ok" in run["message"]


def test_automation_update_api(client):
    r = client.put("/api/automations/fetch_jobs", json={"enabled": True, "mode": "scheduled", "schedule": "07:30"}).json()
    assert r["enabled"] and r["schedule"] == "07:30"
    assert client.put("/api/automations/fetch_jobs", json={"enabled": True, "mode": "scheduled", "schedule": "7am"}).status_code == 422
    r = client.put("/api/automations/score_new_jobs", json={"enabled": False, "mode": "scheduled", "schedule": "09:00"}).json()
    assert r["schedule"] == "after:fetch_jobs"  # chained ones keep their chain


def test_notifications_api(client):
    from app.db import engine
    from notifications.service import notify
    with Session(engine) as s:
        notify(s, "x", "one")
        notify(s, "x", "two")
        s.commit()
    r = client.get("/api/notifications").json()
    assert r["unread"] == 2 and [n["message"] for n in r["items"]] == ["two", "one"]
    client.post(f"/api/notifications/{r['items'][0]['id']}/read")
    assert client.get("/api/notifications").json()["unread"] == 1
    client.post("/api/notifications/read-all")
    assert client.get("/api/notifications").json()["unread"] == 0


# ---------- skill gaps ----------

def test_skill_gaps(client):
    p = client.get("/api/profile").json()
    p.update(skills=["Python"])
    client.put("/api/profile", json=p)
    a = client.post("/api/jobs/manual", json={"title": "A", "company": "c1", "description": "Requirements:\n- Python\n- Docker\n- Kubernetes\n- Teamwork"}).json()["id"]
    b = client.post("/api/jobs/manual", json={"title": "B", "company": "c2", "description": "Requirements:\n- Docker\n- C#/ Java\nNice to have:\n- AWS"}).json()["id"]
    client.post("/api/jobs/manual", json={"title": "C", "company": "c3", "description": "Requirements:\n- Rust"})  # not saved
    for jid in (a, b):
        client.post("/api/applications", json={"job_id": jid})
    r = client.get("/api/skill-gaps").json()
    assert r["jobs_considered"] == 2
    gaps = {g["skill"]: g for g in r["gaps"]}
    assert r["gaps"][0]["skill"] == "Docker" and gaps["Docker"]["required"] == 2
    assert {j["id"] for j in gaps["Docker"]["jobs"]} == {a, b}
    assert gaps["One of: C# / Java"]["required"] == 1 and gaps["AWS"]["preferred"] == 1
    assert "Python" not in gaps and "Rust" not in gaps
    assert [s["skill"] for s in r["soft_skills"]] == ["Teamwork"]  # listed apart, like the breakdown
    scored = client.get("/api/skill-gaps?scope=scored&min_score=0").json()
    assert "Rust" in {g["skill"] for g in scored["gaps"]}
