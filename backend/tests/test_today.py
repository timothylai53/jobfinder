"""Today page data: saved jobs that are ready to apply, or still need a tailored resume."""
from tests.test_ai_flow import BANK, JD


def test_dashboard_lists_saved_jobs_ready_to_apply_or_needing_a_resume(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK, "profile": {"name": "Ali Bin Contoh"}})
    a = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                              "description": JD}).json()["id"]
    b = client.post("/api/jobs/manual", json={"title": "Graduate Developer", "company": "Kedai Contoh",
                                              "description": JD}).json()["id"]
    for jid in (a, b):
        client.post("/api/applications", json={"job_id": jid})
    client.post("/api/documents/resume", json={"job_id": a, "add_original_ids": ["B1"]})
    client.post("/api/documents/resume", json={"job_id": a, "add_original_ids": ["B1", "B2"]})
    d = client.get("/api/dashboard").json()
    assert [(r["job_id"], r["version"]) for r in d["ready_to_apply"]] == [(a, 2)]  # the newest version
    assert [r["job_id"] for r in d["saved_without_resume"]] == [b]
    app_a = next(x for x in client.get("/api/applications").json() if x["job_id"] == a)
    client.patch(f"/api/applications/{app_a['id']}", json={"status": "Applied"})
    assert client.get("/api/dashboard").json()["ready_to_apply"] == []  # applied: no longer a next step


def test_snooze_hides_a_next_step_until_it_expires(client):
    from datetime import date, timedelta
    r = client.post("/api/dashboard/snooze", json={"key": "tailor-3"}).json()
    assert r["until"] == (date.today() + timedelta(days=3)).isoformat()
    assert client.get("/api/dashboard").json()["snoozed"] == {"tailor-3": r["until"]}
    assert client.post("/api/dashboard/snooze", json={"key": "x", "days": 0}).status_code == 422
    client.delete("/api/dashboard/snooze/tailor-3")
    assert client.get("/api/dashboard").json()["snoozed"] == {}


def test_expired_snoozes_are_dropped():
    from datetime import date

    from sqlmodel import Session

    from app.db import engine
    from app.settings_store import _put, get_snoozed
    with Session(engine) as s:
        _put(s, "snoozed_steps", {"old": "2020-01-01", "new": "2999-01-01"})
        assert get_snoozed(s, date.today()) == {"new": "2999-01-01"}


def test_not_interested_hides_the_job_with_that_reason(client):
    jid = client.post("/api/jobs/manual", json={"title": "Junior Dev", "company": "Kedai Contoh", "description": JD}).json()["id"]
    client.patch(f"/api/jobs/{jid}", json={"hidden": True, "hidden_reason": "Not interested"})
    job = client.get(f"/api/jobs/{jid}").json()["job"]
    assert job["hidden"] and job["hidden_reason"] == "Not interested"
    client.patch(f"/api/jobs/{jid}", json={"hidden": False})
    assert client.get(f"/api/jobs/{jid}").json()["job"]["hidden_reason"] == ""


def test_adding_a_missing_skill_to_the_profile_rescores_the_job(client):
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK, "profile": {"name": "Ali Bin Contoh"}})
    jid = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                "description": JD}).json()["id"]

    def docker():
        cats = client.get(f"/api/jobs/{jid}").json()["match"]["breakdown"]["categories"]
        req = next(c for c in cats if c["key"] == "required_skills")
        return next(i["status"] for i in req["items"] if i["name"] == "Docker"), client.get(f"/api/jobs/{jid}").json()["match"]["total"]

    before_status, before = docker()
    assert before_status == "not_met"
    profile = client.get("/api/profile").json()
    client.put("/api/profile", json={**profile, "skills": [*profile["skills"], "Docker"]})  # what "I have this" sends
    after_status, after = docker()
    assert after_status == "met" and after > before
