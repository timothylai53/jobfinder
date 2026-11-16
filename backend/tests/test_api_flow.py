"""End-to-end API flow: upload resume -> import -> paste JD -> score -> tracker -> export/backup."""
from datetime import date, timedelta
from pathlib import Path

from tests.fixtures.make_files import make_pdf

JD = (Path(__file__).parent / "fixtures" / "jds" / "junior_react.txt").read_text(encoding="utf-8")


def import_resume(client, tmp_path):
    pdf = make_pdf(tmp_path / "cv.pdf")
    with pdf.open("rb") as f:
        r = client.post("/api/resumes/parse", files={"file": ("cv.pdf", f, "application/pdf")})
    assert r.status_code == 200, r.text
    draft = r.json()
    assert draft["profile"]["name"] == "Aisyah Tan"
    items = [{k: v for k, v in it.items()} for it in draft["items"]]
    prof = {k: draft["profile"][k] for k in ("name", "email", "education_level", "education_field",
                                             "degree_status", "languages", "skills")}
    prof["expected_graduation"] = "2027-06-01"
    r = client.post("/api/resumes/import", json={"name": "Software Dev", "file_path": draft["file_path"],
                                                 "raw_text": draft["raw_text"], "profile": prof, "items": items})
    assert r.status_code == 200, r.text
    return r.json()


def test_full_phase1_flow(client, tmp_path):
    res = import_resume(client, tmp_path)
    assert res["item_codes"][0] == "B1"
    bank = client.get("/api/experience").json()
    assert [b["code"] for b in bank] == res["item_codes"]
    assert all(b["resume_ids"] == [res["resume_id"]] for b in bank)

    profile = client.get("/api/profile").json()
    assert profile["degree_status"] == "in_progress"
    profile.update(preferred_locations=["Kuala Lumpur"], years_of_experience=0)
    assert client.put("/api/profile", json=profile).status_code == 200

    r = client.post("/api/jobs/manual", json={"title": "Junior Frontend Developer", "company": "Acme Digital Sdn Bhd",
                                              "location": "Kuala Lumpur", "description": JD})
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    assert r.json()["duplicate"] is False and r.json()["hidden"] is False

    detail = client.get(f"/api/jobs/{job_id}").json()
    bd = detail["match"]["breakdown"]
    assert detail["match"]["total"] == bd["total"] > 0
    cats = {c["key"]: c for c in bd["categories"]}
    edu = cats["education"]
    assert edu["status"] == "partial" and "in progress" in edu["note"]
    react = next(i for i in cats["preferred_skills"]["items"] if i["name"] == "React")  # from Responsibilities
    assert react["status"] == "met" and react["evidence"]  # traced back to a bank item / profile

    # duplicate paste merges instead of creating a second job
    r = client.post("/api/jobs/manual", json={"title": "Junior Frontend Developer (Urgent)", "company": "ACME DIGITAL",
                                              "location": "Kuala Lumpur, Malaysia", "description": JD,
                                              "url": "https://example.com/job/1"})
    assert r.json()["id"] == job_id and r.json()["duplicate"] is True
    assert client.get(f"/api/jobs/{job_id}").json()["job"]["urls"] == ["https://example.com/job/1"]

    # save to tracker, move through statuses
    app_id = client.post("/api/applications", json={"job_id": job_id}).json()["id"]
    assert client.post("/api/applications", json={"job_id": job_id}).json() == {"id": app_id, "existing": True}
    a = client.patch(f"/api/applications/{app_id}", json={"status": "Applied", "notes": "Sent via site"}).json()
    assert a["applied_at"] == date.today().isoformat()
    assert a["follow_up_at"] == (date.today() + timedelta(days=7)).isoformat()
    client.patch(f"/api/applications/{app_id}", json={"status": "Interview"})
    hist = client.get(f"/api/applications/{app_id}/history").json()
    assert [(h["from_status"], h["to_status"]) for h in hist] == [(None, "Saved"), ("Saved", "Applied"), ("Applied", "Interview")]
    assert client.patch(f"/api/applications/{app_id}", json={"status": "Bogus"}).status_code == 422

    dash = client.get("/api/dashboard").json()
    assert dash["status_counts"]["Interview"] == 1
    assert dash["response_rate"] == 100.0
    assert dash["applications_per_week"][-1]["count"] == 1

    # export + backup
    r = client.get("/api/export/xlsx")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = client.get("/api/export/jobs.csv")
    assert "Junior Frontend Developer" in r.content.decode("utf-8-sig")
    r = client.post("/api/backup")
    assert Path(r.json()["path"]).exists()


def test_filter_rules_hide_manual_jobs_and_reapply(client):
    r = client.post("/api/jobs/manual", json={"title": "Senior Backend Engineer", "company": "X", "description": "Python"})
    assert r.json()["hidden"] is True and 'Senior' in r.json()["hidden_reason"]
    jid = r.json()["id"]
    rules = client.get("/api/filters").json()
    title_rule = next(x for x in rules if x["type"] == "title_contains")
    client.put(f"/api/filters/{title_rule['id']}", json={**title_rule, "enabled": False})
    assert client.get(f"/api/jobs/{jid}").json()["job"]["hidden"] is False
    # manual hide survives rule re-application
    client.patch(f"/api/jobs/{jid}", json={"hidden": True})
    client.put(f"/api/filters/{title_rule['id']}", json={**title_rule, "enabled": False, "value": "Lead"})
    assert client.get(f"/api/jobs/{jid}").json()["job"]["hidden_reason"] == "Hidden manually"
    assert client.post("/api/filters", json={"type": "min_years_over", "value": "abc"}).status_code == 422


def test_scoring_settings_change_rescores(client):
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "description": "Requirements:\n- Kotlin"}).json()["id"]
    before = client.get(f"/api/jobs/{jid}").json()["match"]["total"]
    s = client.get("/api/settings").json()
    s["scoring"]["weights"]["required_skills"] = 100
    assert client.put("/api/settings", json=s).status_code == 200
    after = client.get(f"/api/jobs/{jid}").json()["match"]["total"]
    assert after < before  # missing Kotlin now weighs more


def test_skill_crud_and_bank_codes_never_reused(client):
    r = client.post("/api/skills", json={"name": "Odoo", "category": "framework", "aliases": ["OpenERP", "Odoo"]})
    assert r.status_code == 200 and r.json()["aliases"] == ["OpenERP"]
    assert client.post("/api/skills", json={"name": "odoo"}).status_code == 409
    a = client.post("/api/experience", json={"type": "project", "title": "A"}).json()
    b = client.post("/api/experience", json={"type": "project", "title": "B"}).json()
    client.delete(f"/api/experience/{b['id']}")
    c = client.post("/api/experience", json={"type": "project", "title": "C"}).json()
    assert (a["code"], b["code"], c["code"]) == ("B1", "B2", "B3")


def test_parse_rejects_bad_files(client):
    r = client.post("/api/resumes/parse", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert r.status_code == 422
    r = client.post("/api/resumes/parse", files={"file": ("cv.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 422
