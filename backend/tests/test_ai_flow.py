"""Copy-Paste AI flow end to end through the API, with saved fake replies (no AI website is ever contacted):
prompt -> paste reply -> validate -> fabrication guard -> save accepted content as document versions."""
from pathlib import Path

import pytest
from sqlmodel import Session, select

from models import AITask, Document, MatchResult

FIX = Path(__file__).parent / "fixtures" / "ai"
JD = """Junior Software Engineer
Requirements:
- Degree in Computer Science or related field
- Python and SQL
- React
- Docker
Nice to have:
- Kubernetes
Fresh graduates are welcome."""

BANK = [
    {"type": "work", "title": "Software Engineering Intern", "organization": "Contoh Tech Sdn Bhd", "start": "Jun 2024",
     "end": "Sep 2024", "bullets": ["Developed REST APIs in Python and Flask", "Wrote SQL queries for reporting"],
     "skills": ["Python", "Flask", "SQL"]},
    {"type": "project", "title": "Campus Food Ordering App", "organization": "Universiti Contoh", "start": "2023",
     "end": "2023", "bullets": ["Built a React front end with a Node.js backend"], "skills": ["React", "Node.js", "Git"]},
    {"type": "education", "title": "Bachelor of Software Engineering", "organization": "Universiti Contoh",
     "start": "2021", "end": "2025", "bullets": [], "skills": []},
    {"type": "certification", "title": "Oracle Certified Associate, Java SE 8 Programmer", "organization": "Oracle",
     "start": "", "end": "2024", "bullets": [], "skills": ["Java"]},
    {"type": "publication", "title": "A Study of Queue Scheduling in Campus Systems",
     "organization": "Journal of Contoh Computing", "start": "", "end": "2024", "bullets": [], "skills": []},
]


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


@pytest.fixture
def setup(client):
    r = client.post("/api/resumes/import", json={
        "name": "Fake resume", "items": BANK,
        "profile": {"name": "Ali Bin Contoh", "email": "ali.contoh@example.com", "phone": "012-345 6789",
                    "location": "Shah Alam, Selangor", "languages": ["English", "Malay"]}}).json()
    assert r["item_codes"] == ["B1", "B2", "B3", "B4", "B5"]
    job_id = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                   "location": "Kuala Lumpur", "description": JD}).json()["id"]
    return client, job_id


def new_task(client, job_id, task="tailor_resume", **kw):
    r = client.post("/api/ai/tasks", json={"task": task, "job_id": job_id, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ---------- the prompt ----------

def test_prompt_has_bank_ids_jd_profile_rules_and_schema_but_no_contacts(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    p = t["prompt"]
    assert t["status"] == "waiting" and t["provider"] == "copy_paste"
    for code in ("[B1] work: Software Engineering Intern", "[B4] certification:", "[B5] publication:"):
        assert code in p
    assert "Docker" in p and "Syarikat Contoh Bhd" in p  # the JD snapshot
    assert "Never invent employers, dates, numbers, skills, or achievements." in p
    assert "Every resume bullet must reference the ID" in p
    assert "exactly one JSON object inside a single ```json code block" in p
    assert '"source_id": "B3"' in p  # the schema example
    assert "Ali Bin Contoh" in p and "ali.contoh@example.com" not in p and "012-345 6789" not in p


@pytest.mark.parametrize("task", ["deep_analysis", "cover_letter", "interview_prep"])
def test_every_job_task_builds_a_prompt(setup, task):
    client, job_id = setup
    p = new_task(client, job_id, task)["prompt"]
    assert "[B1]" in p and "Junior Software Engineer" in p and "```json" in p


# ---------- reply -> validate -> guard ----------

def test_valid_reply_parses_without_flags(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_valid.txt")}).json()
    assert t["status"] == "parsed" and t["errors"] == [] and t["flags"] == []
    assert t["result"]["sections"][3]["section"] == "Certifications"


def test_broken_json_is_repaired_and_reported(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_broken_json.txt")}).json()
    assert t["status"] == "parsed" and "removed trailing commas" in t["repairs"]


def test_fabrication_guard_flags_ids_and_skills(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_fabricated.txt")}).json()
    assert t["status"] == "parsed"
    flags = {(f["path"], f["kind"]) for f in t["flags"]}
    assert ("sections.0.items.1", "unknown_id") in flags  # B99
    assert ("sections.0.items.2", "missing_id") in flags  # no source_id
    assert ("sections.0.items.3", "unknown_skill") in flags  # "deployed it with Docker"
    assert ("skills_order.1", "unknown_skill") in flags and ("skills_order.2", "unknown_skill") in flags
    assert ("summary", "unknown_skill") in flags  # Kubernetes / AWS in the summary
    assert ("omitted_ids.0", "unknown_id") in flags
    assert not any(f["path"] == "sections.0.items.0" for f in t["flags"])  # the honest bullet is clean
    assert not any(f["path"] == "skills_order.0" for f in t["flags"])  # Python is in the bank


def _by_path(flags: list[dict], kind: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in flags:
        if f["kind"] == kind:
            out.setdefault(f["path"], []).append(f["message"])
    return out


def test_guard_flags_new_numbers_in_tailored_resume(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_numbers_skills.txt")}).json()
    nums = _by_path(t["flags"], "new_number")
    assert len(nums["sections.0.items.0"]) == 2  # 500+ and 40%, not in B1
    assert "'500+'" in nums["sections.0.items.0"][0] and "'40%'" in nums["sections.0.items.0"][1]
    assert len(nums["sections.1.items.0"]) == 2  # 3x and RM 2k, not in B2
    assert "'RM 2k'" in nums["sections.1.items.0"][1]
    assert "sections.0.items.1" not in nums  # Jun 2024 - Sep 2024 are B1's own dates
    assert "sections.2.items.0" not in nums  # "Java SE 8" and 2024 are in B4
    assert [m.split("'")[1] for m in nums["summary"]] == ["2", "10"]  # 2025 is in B3, so only 2 and 10
    assert all(f["kind"] != "new_number" or f["path"] in nums for f in t["flags"])


def test_guard_flags_skills_not_in_the_source_item(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_numbers_skills.txt")}).json()
    amber = _by_path(t["flags"], "skill_not_in_item")
    assert amber["sections.0.items.2"] == ["Git isn't in B1: is that true for this job?"]  # Git is only in B2
    assert sorted(amber["sections.1.items.1"]) == ["Flask isn't in B2: is that true for this project?",
                                                   "Python isn't in B2: is that true for this project?"]
    assert "sections.0.items.0" not in amber  # Python and REST are in B1
    # Docker isn't in the bank at all: red unknown_skill only, no amber on top
    assert "sections.1.items.2" not in amber
    assert ("sections.1.items.2", "unknown_skill") in {(f["path"], f["kind"]) for f in t["flags"]}
    # amber and red number flags don't block saving: only missing / unknown IDs do
    body = {"job_id": job_id, "ai_task_id": t["id"], "summary": "", "skills": [],
            "sections": [{"section": "Projects", "items": [{"source_id": "B2", "text": "Built a React front end with a Python Flask API"}]}]}
    assert client.post("/api/documents/resume", json=body).status_code == 200


def test_guard_flags_new_numbers_in_cover_letter(setup):
    client, job_id = setup
    t = new_task(client, job_id, "cover_letter")
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("cover_letter_numbers.txt")}).json()
    nums = _by_path(t["flags"], "new_number")
    assert list(nums) == ["paragraphs.1", "paragraphs.2"]
    assert "'10,000'" in nums["paragraphs.1"][0] and len(nums["paragraphs.1"]) == 1  # 2024 is in the bank
    assert "'30 percent'" in nums["paragraphs.2"][0] and len(nums["paragraphs.2"]) == 1  # 2025 is in B3


def test_profile_numbers_count_for_summary(setup):
    client, job_id = setup
    profile = client.get("/api/profile").json()
    assert client.put("/api/profile", json={**profile, "years_of_experience": 1, "years_confirmed": True}).status_code == 200
    t = new_task(client, job_id)
    reply = {"summary": "Developer with 1 year of experience and 2 internships.", "skills_order": [],
             "sections": [{"section": "Experience", "items": [{"source_id": "B1", "text": "Developed REST APIs"}]}]}
    t = client.post(f"/api/ai/tasks/{t['id']}/edited", json={"data": reply}).json()
    assert [f["message"].split("'")[1] for f in t["flags"] if f["kind"] == "new_number"] == ["2"]


@pytest.mark.parametrize("text,expected", [
    ("cut load time by 40% for 500+ users", [("40%", (40.0, "pct")), ("500+", (500.0, "n"))]),
    ("3x faster, saved RM 2k", [("3x", (3.0, "times")), ("RM 2k", (2000.0, "n"))]),
    ("RM2,000 and 2.5 million", [("RM2,000", (2000.0, "n")), ("2.5 million", (2500000.0, "n"))]),
    ("30 percent", [("30 percent", (30.0, "pct"))]),
    ("HTML5, ES6, B12, v2.0", []),  # digits glued to letters aren't numbers
])
def test_numbers_are_read_as_written(text, expected):
    from ai.guard import numbers
    assert numbers(text) == expected


def test_schema_error_gives_paths_and_a_fixup_prompt(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_schema_error.txt")}).json()
    assert t["status"] == "invalid" and t["result"] is None
    assert {"skills_order", "sections.0.items.0.text"} <= {e["path"] for e in t["errors"]}
    fix = client.get(f"/api/ai/tasks/{t['id']}/fixup").json()["prompt"]
    assert "sections.0.items.0.text: Field required" in fix and '"skills_order": "Python, SQL"' in fix
    assert "```json" in fix  # the schema again
    # editing the JSON by hand in the review screen and re-validating
    fixed = {"summary": "Graduate developer.", "skills_order": ["Python"],
             "sections": [{"section": "Experience", "items": [{"source_id": "B1", "text": "Developed REST APIs"}]}]}
    t = client.post(f"/api/ai/tasks/{t['id']}/edited", json={"data": fixed}).json()
    assert t["status"] == "parsed" and t["errors"] == []


def test_deep_analysis_and_interview_prep_flags_and_saving(setup):
    client, job_id = setup
    t = new_task(client, job_id, "deep_analysis")
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("deep_analysis_valid.txt")}).json()
    kinds = {(f["path"], f["kind"]) for f in t["flags"]}
    assert ("requirements.5.evidence_ids.1", "unknown_id") in kinds  # B42
    assert ("requirements.4", "missing_id") in kinds  # "met" with no evidence
    doc = client.post("/api/documents/from-task", json={"ai_task_id": t["id"]}).json()
    assert doc["type"] == "deep_analysis" and doc["version"] == 1 and doc["content"]["overall_fit"] == 68
    assert doc["content"]["flags"]  # the flags stay with the saved analysis
    from app.db import engine
    with Session(engine) as s:
        deep = s.exec(select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.method == "deep")).one()
        assert deep.total == 68
        assert s.exec(select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.method == "quick")).one()
        assert s.get(AITask, t["id"]).status == "saved"
    t = new_task(client, job_id, "interview_prep")
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("interview_prep_valid.txt")}).json()
    assert {f["path"] for f in t["flags"]} == {"questions.2.suggested_points_ids.1"}  # B77
    assert client.post("/api/documents/from-task", json={"ai_task_id": t["id"]}).json()["type"] == "interview_prep"


# ---------- saving a tailored resume ----------

def _accepted(result: dict, drop: set[tuple[int, int]] = frozenset()) -> list[dict]:
    return [{"section": s["section"], "items": [it for j, it in enumerate(s["items"]) if (i, j) not in drop]}
            for i, s in enumerate(result["sections"])]


def test_save_resume_versions_with_certifications_and_publications(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_valid.txt")}).json()
    body = {"job_id": job_id, "ai_task_id": t["id"], "summary": t["result"]["summary"],
            "skills": t["result"]["skills_order"], "sections": _accepted(t["result"], drop={(0, 1)})}
    doc = client.post("/api/documents/resume", json=body).json()
    assert doc["version"] == 1 and doc["source"] == "copy_paste"
    secs = {s["section"]: s["entries"] for s in doc["content"]["sections"]}
    assert list(secs) == ["Experience", "Projects", "Education", "Certifications", "Publications"]
    intern = secs["Experience"][0]
    assert (intern["title"], intern["organization"], intern["start"]) == ("Software Engineering Intern", "Contoh Tech Sdn Bhd", "Jun 2024")
    assert intern["bullets"] == ["Developed REST APIs in Python (Flask) used by the internal reporting team"]  # rejected one is gone
    assert secs["Certifications"][0]["title"].startswith("Oracle Certified Associate") and secs["Certifications"][0]["bullets"] == []
    assert secs["Publications"][0]["type"] == "publication"
    assert doc["content"]["header"]["name"] == "Ali Bin Contoh"
    # a second save is version 2
    assert client.post("/api/documents/resume", json={**body, "ai_task_id": None}).json()["version"] == 2
    html = client.get(f"/api/documents/{doc['id']}/html").text
    for heading in ("Experience", "Projects", "Education", "Certifications", "Publications", "Skills", "Summary"):
        assert f"<h2>{heading}</h2>" in html
    assert "<table" not in html and "<img" not in html  # ATS-friendly


def test_unknown_or_missing_ids_cannot_be_saved(setup):
    client, job_id = setup
    body = {"job_id": job_id, "sections": [{"section": "Experience", "items": [{"source_id": "B99", "text": "Led a team at Google"}]}]}
    r = client.post("/api/documents/resume", json=body)
    assert r.status_code == 422 and "not in your Experience Bank" in r.json()["detail"]
    body["sections"][0]["items"][0]["source_id"] = ""
    assert client.post("/api/documents/resume", json=body).status_code == 422


def test_add_original_items_the_ai_left_out(setup):
    client, job_id = setup
    body = {"job_id": job_id, "sections": [{"section": "Projects", "items": [{"source_id": "B2", "text": "Built a React app"}]}],
            "add_original_ids": ["B1", "B3"]}
    doc = client.post("/api/documents/resume", json=body).json()
    secs = {s["section"]: s["entries"] for s in doc["content"]["sections"]}
    assert secs["Experience"][0]["bullets"] == ["Developed REST APIs in Python and Flask", "Wrote SQL queries for reporting"]
    assert "Education" in secs


# ---------- cover letters ----------

def test_cover_letter_from_reply_flags_unclaimed_skills(setup):
    client, job_id = setup
    t = new_task(client, job_id, "cover_letter")
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("cover_letter_valid.txt")}).json()
    assert [f["path"] for f in t["flags"]] == ["paragraphs.2"]  # "learning Kubernetes"
    r = t["result"]
    doc = client.post("/api/documents/cover-letter", json={"job_id": job_id, "ai_task_id": t["id"], **r}).json()
    assert doc["type"] == "cover_letter" and doc["content"]["company"] == "Syarikat Contoh Bhd"
    assert "Syarikat Contoh Bhd" in client.get(f"/api/documents/{doc['id']}/html").text


def test_template_cover_letter_works_with_ai_off(setup):
    client, job_id = setup
    s = client.get("/api/ai/settings").json()
    client.put("/api/ai/settings", json={**s, "mode": "off"})
    assert client.post("/api/ai/tasks", json={"task": "cover_letter", "job_id": job_id}).status_code == 409
    d = client.post("/api/documents/cover-letter/template-draft", json={"job_id": job_id}).json()
    text = " ".join(d["paragraphs"])
    assert "Junior Software Engineer position at Syarikat Contoh Bhd" in text
    assert d["skills"][:2] == ["Python", "SQL"] and "Docker" not in d["skills"]
    assert d["used_ids"] == ["B1", "B2"]
    assert "In my role “Software Engineering Intern” at Contoh Tech Sdn Bhd, I developed REST APIs in Python and Flask." in text
    chosen = client.post("/api/documents/cover-letter/template-draft", json={"job_id": job_id, "item_codes": ["B2"]}).json()
    assert chosen["used_ids"] == ["B2"]
    doc = client.post("/api/documents/cover-letter", json={"job_id": job_id, "source": "template", **d}).json()
    assert doc["source"] == "template" and doc["version"] == 1


# ---------- applications record the versions sent ----------

def test_application_links_versions_of_its_own_job(setup):
    client, job_id = setup
    resume = client.post("/api/documents/resume", json={"job_id": job_id, "add_original_ids": ["B1"]}).json()
    letter = client.post("/api/documents/cover-letter", json={"job_id": job_id, "greeting": "Dear Hiring Manager,",
                                                              "paragraphs": ["Hello."], "closing": "Sincerely,"}).json()
    app_id = client.post("/api/applications", json={"job_id": job_id}).json()["id"]
    a = client.patch(f"/api/applications/{app_id}", json={"resume_version_id": resume["id"],
                                                         "cover_letter_version_id": letter["id"]}).json()
    assert (a["resume_version_id"], a["cover_letter_version_id"]) == (resume["id"], letter["id"])
    assert client.patch(f"/api/applications/{app_id}", json={"resume_version_id": letter["id"]}).status_code == 422
    assert client.delete(f"/api/documents/{resume['id']}").status_code == 409  # it was sent: keep it
    client.patch(f"/api/applications/{app_id}", json={"resume_version_id": None})
    assert client.delete(f"/api/documents/{resume['id']}").status_code == 200


# ---------- parse_resume ----------

def test_parse_resume_flags_what_the_resume_does_not_say(client):
    text = fx("resume_text_fake.txt")
    t = client.post("/api/ai/tasks", json={"task": "parse_resume", "resume_text": text}).json()
    assert "Ali Bin Contoh" in t["prompt"] and "References section" in t["prompt"]
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("parse_resume_reply.txt")}).json()
    assert t["status"] == "parsed"
    flagged = {f["path"] for f in t["flags"]}
    assert {"items.2.title", "items.2.organization", "profile.skills.2"} <= flagged  # Senior Architect, Google, Kubernetes
    assert not any(p.startswith(("items.0", "items.1")) for p in flagged)


def test_parse_resume_needs_text(client):
    assert client.post("/api/ai/tasks", json={"task": "parse_resume", "resume_text": "  "}).status_code == 409


# ---------- prompt templates are editable files ----------

def test_templates_edit_reset_and_rules_cannot_be_lost(setup):
    client, job_id = setup
    names = {t["name"] for t in client.get("/api/ai/templates").json()}
    assert names == {"parse_resume", "deep_analysis", "tailor_resume", "cover_letter", "interview_prep", "fixup"}
    r = client.put("/api/ai/templates/cover_letter", json={"text": "Write a very short letter.\n\n{{job}}"}).json()
    assert r["edited"] is True
    p = new_task(client, job_id, "cover_letter")["prompt"]
    assert p.startswith("Write a very short letter.")
    assert "Never invent employers" in p and "[B1]" in p and "```json" in p  # rules, bank, schema appended
    client.post("/api/ai/templates/cover_letter/reset")
    assert not next(t for t in client.get("/api/ai/templates").json() if t["name"] == "cover_letter")["edited"]
    assert client.put("/api/ai/templates/cover_letter", json={"text": "  "}).status_code == 422
    assert client.put("/api/ai/templates/nope", json={"text": "x"}).status_code == 404
    from ai.prompt_templates import HERE
    assert not (HERE / "cover_letter.md").exists()  # tests never write into the repo


def test_ai_off_hides_tasks_but_documents_still_list(setup):
    client, job_id = setup
    client.put("/api/ai/settings", json={**client.get("/api/ai/settings").json(), "mode": "off"})
    r = client.post("/api/ai/tasks", json={"task": "tailor_resume", "job_id": job_id})
    assert r.status_code == 409 and "switched off" in r.json()["detail"]
    assert client.get(f"/api/jobs/{job_id}/documents").json() == []


def test_documents_list_per_job_newest_first(setup):
    client, job_id = setup
    for _ in range(2):
        client.post("/api/documents/resume", json={"job_id": job_id, "add_original_ids": ["B1"]})
    docs = client.get(f"/api/jobs/{job_id}/documents").json()
    assert [(d["type"], d["version"]) for d in docs] == [("resume", 2), ("resume", 1)]
    from app.db import engine
    with Session(engine) as s:
        assert len(s.exec(select(Document)).all()) == 2


# ---------- tailor_resume: one bullet per item, no repeated header ----------

def test_tailor_prompt_asks_for_one_bullet_per_item_without_header(setup):
    client, job_id = setup
    p = new_task(client, job_id)["prompt"]
    assert "Each item's \"text\" is ONE bullet" in p and "Never repeat the item's title, organization or dates" in p
    assert '{"source_id": "B2", "text": "A second bullet from B2, as its own item"}' in p


def test_repeated_header_is_stripped_and_merged_bullets_warned(setup):
    client, job_id = setup
    t = new_task(client, job_id)
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("tailor_header_merged.txt")}).json()
    items = t["result"]["sections"][0]["items"]
    assert items[0]["text"] == "Developed REST APIs in Python and Flask. Wrote SQL queries for reporting."
    assert items[1]["text"] == "Wrote SQL queries for weekly reporting"
    kinds = {(f["path"], f["kind"]) for f in t["flags"]}
    assert ("sections.0.items.0", "header_removed") in kinds and ("sections.0.items.1", "header_removed") in kinds
    removed = next(f["message"] for f in t["flags"] if f["kind"] == "header_removed")
    assert "Software Engineering Intern, Contoh Tech Sdn Bhd, Jun 2024 - Sep 2024" in removed
    assert ("sections.0.items.0", "several_bullets") in kinds and ("sections.0.items.1", "several_bullets") not in kinds
    # a bullet that merely starts with the item's title, and "e.g.", are left alone
    projects = t["result"]["sections"][1]["items"]
    assert projects[1]["text"].startswith("Campus Food Ordering App is used")
    assert not any(f["path"].startswith("sections.1") for f in t["flags"])


@pytest.mark.parametrize("text,expected", [
    ("Intern, Contoh, Mar 2025 - Present. Redesigned the flow", ("Redesigned the flow", "Intern, Contoh, Mar 2025 - Present")),
    ("Intern at Contoh (October 2026 to present): redesigned the flow", ("Redesigned the flow", "Intern at Contoh (October 2026 to present)")),
    ("Intern: built dashboards", ("Built dashboards", "Intern")),
    ("Intern work included dashboards", ("Intern work included dashboards", "")),
    ("Contoh's API was rebuilt", ("Contoh's API was rebuilt", "")),
    ("Mar 2025 - Present: built X", ("Mar 2025 - Present: built X", "")),
    ("Intern, Contoh", ("Intern, Contoh", "")),  # nothing left after the header: kept as written
])
def test_strip_header(text, expected):
    from ai.guard import strip_header
    assert strip_header(text, ["Intern", "Contoh", "Mar 2025", "Present"]) == expected


def test_same_source_id_prints_under_one_header(setup):
    client, job_id = setup
    body = {"job_id": job_id, "sections": [
        {"section": "Experience", "items": [{"source_id": "B1", "text": "Developed REST APIs"},
                                            {"source_id": "B2", "text": "Built a React app"},
                                            {"source_id": "b1", "text": "Wrote SQL queries"}]}]}
    doc = client.post("/api/documents/resume", json=body).json()
    entries = doc["content"]["sections"][0]["entries"]
    assert [(e["source_id"], e["bullets"]) for e in entries] == [
        ("B1", ["Developed REST APIs", "Wrote SQL queries"]), ("B2", ["Built a React app"])]
    html = client.get(f"/api/documents/{doc['id']}/html").text
    assert html.count("Software Engineering Intern") == 1 and html.count("Jun 2024") == 1


# ---------- profile links in the header ----------

@pytest.mark.parametrize("url,expected", [
    ("https://www.linkedin.com/in/ali-contoh/", {"href": "https://www.linkedin.com/in/ali-contoh/", "text": "linkedin.com/in/ali-contoh"}),
    ("github.com/alicontoh", {"href": "https://github.com/alicontoh", "text": "github.com/alicontoh"}),
    ("javascript:alert(1)", None),
    ("not a url", None),
    ("", None),
])
def test_profile_link(url, expected):
    from documents.service import link
    assert link(url) == expected


def test_links_in_resume_and_cover_letter_headers_not_in_prompts(setup):
    client, job_id = setup
    profile = client.get("/api/profile").json()
    client.put("/api/profile", json={**profile, "linkedin_url": "https://www.linkedin.com/in/ali-contoh",
                                     "github_url": "github.com/alicontoh", "portfolio_url": ""})
    resume = client.post("/api/documents/resume", json={"job_id": job_id, "add_original_ids": ["B1"]}).json()
    html = client.get(f"/api/documents/{resume['id']}/html").text
    assert '<a href="https://www.linkedin.com/in/ali-contoh">linkedin.com/in/ali-contoh</a> | ' \
           '<a href="https://github.com/alicontoh">github.com/alicontoh</a>' in html
    letter = client.post("/api/documents/cover-letter", json={"job_id": job_id, "greeting": "Dear Hiring Manager,",
                                                              "paragraphs": ["I am applying."], "closing": "Sincerely,"}).json()
    assert '<a href="https://github.com/alicontoh">github.com/alicontoh</a>' in client.get(f"/api/documents/{letter['id']}/html").text
    assert "alicontoh" not in new_task(client, job_id)["prompt"]  # links stay out of AI prompts


def test_placeholders_copied_from_the_example_are_flagged(setup):
    """qwen2.5:3b returned the example's "..." as the summary (real run, 22 Nov): it's flagged, and the prompt warns."""
    client, job_id = setup
    t = new_task(client, job_id)
    assert 'Never return "..." as a value.' in t["prompt"]
    reply = {"summary": "...", "skills_order": ["Python"],
             "sections": [{"section": "Experience", "items": [{"source_id": "B1", "text": "…"},
                                                              {"source_id": "B1", "text": "Developed REST APIs"}]}]}
    t = client.post(f"/api/ai/tasks/{t['id']}/edited", json={"data": reply}).json()
    flagged = {(f["path"], f["kind"]) for f in t["flags"]}
    assert {("summary", "placeholder"), ("sections.0.items.0.text", "placeholder")} <= flagged
    assert not any(f["path"] == "sections.0.items.1" for f in t["flags"])
