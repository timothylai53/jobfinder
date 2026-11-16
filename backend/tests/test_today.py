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
