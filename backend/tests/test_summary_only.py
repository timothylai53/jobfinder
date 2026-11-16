""""Summary only" jobs (saved from a search card): flagged as a rough score, never high-match alerted, and
upgraded in place by pasting the full JD. No network."""
from sqlmodel import Session, select

from models import Job, MatchResult, Notification
from scheduler.automations import run_automation
from sources.ingest import SUMMARY_ONLY

FULL_JD = "Requirements:\n- Python\n- SQL\n- 1 year of experience"


def _engine():
    from app.db import engine
    return engine


def _profile(client):
    profile = client.get("/api/profile").json()
    profile.update(skills=["Python", "SQL"], years_confirmed=True)
    client.put("/api/profile", json=profile)


def _summary_job(client, **kw) -> int:
    body = {"title": "Dev", "company": "Contoh", "url": "https://my.jobstreet.com/job/90000009",
            "description": f"Python and SQL role\n- Python\n- SQL\n- Fresh graduates welcome\n\n{SUMMARY_ONLY}", **kw}
    return client.post("/api/jobs/manual", json=body).json()["id"]


def test_summary_only_is_flagged_in_list_and_detail(client):
    sid = _summary_job(client)
    fid = client.post("/api/jobs/manual", json={"title": "Other", "company": "B", "description": FULL_JD}).json()["id"]
    flags = {j["id"]: j["summary_only"] for j in client.get("/api/jobs").json()}
    assert flags == {sid: True, fid: False}
    assert client.get(f"/api/jobs/{sid}").json()["summary_only"] is True
    assert client.get(f"/api/jobs/{fid}").json()["summary_only"] is False


def test_high_match_alert_skips_summary_only_until_the_full_jd_is_pasted(client):
    _profile(client)
    sid = _summary_job(client)
    assert client.get(f"/api/jobs/{sid}").json()["match"]["total"] >= 70  # the rough score is high...
    run_automation(_engine(), "high_match_alert")
    with Session(_engine()) as s:
        assert s.exec(select(Notification).where(Notification.type == "high_match")).all() == []  # ...but no alert
        assert s.get(Job, sid).high_match_notified is False  # not marked: it can still alert once complete
    client.post(f"/api/jobs/{sid}/full-description", json={"description": FULL_JD})
    run_automation(_engine(), "high_match_alert")
    with Session(_engine()) as s:
        assert len(s.exec(select(Notification).where(Notification.type == "high_match")).all()) == 1


def test_full_description_updates_the_same_job_and_rescores(client):
    _profile(client)
    sid = _summary_job(client, salary_min=None, job_type="Full time")
    before = client.get(f"/api/jobs/{sid}").json()["match"]["breakdown"]
    r = client.post(f"/api/jobs/{sid}/full-description", json={
        "description": FULL_JD + "\n- Docker", "salary_min": 4000, "salary_max": 5000, "salary_currency": "MYR",
        "job_type": "Contract", "location": "Cyberjaya, Selangor"}).json()
    assert r["ok"] is True and isinstance(r["score"], int)
    with Session(_engine()) as s:
        jobs = s.exec(select(Job)).all()
        assert len(jobs) == 1  # updated in place, never a new job
        job = jobs[0]
        assert job.description == FULL_JD + "\n- Docker" and SUMMARY_ONLY not in job.description
        assert (job.salary_min, job.salary_max, job.location) == (4000, 5000, "Cyberjaya, Selangor")  # blanks filled
        assert job.job_type == "Full time"  # existing values are kept
        assert job.urls == ["https://my.jobstreet.com/job/90000009"]
        assert len(s.exec(select(MatchResult).where(MatchResult.job_id == sid)).all()) == 1
    detail = client.get(f"/api/jobs/{sid}").json()
    assert detail["summary_only"] is False and detail["match"]["breakdown"] != before
    assert "Docker" in str(detail["match"]["breakdown"]) and "Docker" not in str(before)  # scored from the full JD


def test_full_description_reapplies_filter_rules(client):
    sid = _summary_job(client)
    rules = client.get("/api/filters").json()
    kw = next((r for r in rules if r["type"] == "keyword_in_jd"), None)
    if kw is None:
        client.post("/api/filters", json={"type": "keyword_in_jd", "value": "night shift", "enabled": True})
    else:
        client.put(f"/api/filters/{kw['id']}", json={**kw, "value": "night shift", "enabled": True})
    r = client.post(f"/api/jobs/{sid}/full-description", json={"description": FULL_JD + "\nNight shift required."}).json()
    assert r["hidden"] is True and "night shift" in r["hidden_reason"].lower()


def test_full_description_rejects_empty_or_summary_text(client):
    sid = _summary_job(client)
    assert client.post(f"/api/jobs/{sid}/full-description", json={"description": "  "}).status_code == 422
    assert client.post(f"/api/jobs/{sid}/full-description", json={"description": f"x\n{SUMMARY_ONLY}"}).status_code == 422
    assert client.post("/api/jobs/9999/full-description", json={"description": FULL_JD}).status_code == 404
