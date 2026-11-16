"""Resume layout from a real resume (anonymised: fake names, contacts and organisations).

Covers: duplicate re-imports, several projects with a tech-stack line, a References section,
a title wrapped mid-bracket, and MUET listed under Education.
"""
from pathlib import Path

import pytest

from resume_parser.sections import join_wrapped, parse_resume_text
from skills.matcher import SkillMatcher
from skills.service import load_seed
from tests.fixtures.make_files import make_docx

LAYOUT = Path(__file__).parent / "fixtures" / "resume_layout_2.txt"
REFEREE_BITS = ("Aminah", "aminah.contoh@example.edu.my", "+60 3-0000 0000", "Senior Lecturer")


@pytest.fixture(scope="module")
def draft():
    return parse_resume_text(LAYOUT.read_text(encoding="utf-8"), SkillMatcher(load_seed()))


def of_type(draft, t):
    return [i for i in draft["items"] if i["type"] == t]


def test_each_project_title_starts_a_new_item(draft):
    projects = of_type(draft, "project")
    assert [p["title"] for p in projects] == [
        "Web-Based Clinic Booking System", "Campus Lost & Found App", "Personal Portfolio Website"]
    assert projects[0]["organization"] == "Final Year Project (Silver Award)"


def test_tech_stack_line_goes_to_skills_not_bullets(draft):
    clinic, lost_found, portfolio = of_type(draft, "project")
    assert clinic["skills"] == ["Vue.js", "Node.js", "MongoDB", "Express.js", "Tailwind CSS"]  # no stray "CSS"
    assert clinic["bullets"] == ["A web system for a clinic to manage doctors, bookings and reminders, "
                                   "with an admin dashboard and online payment."]  # wrapped line joined
    assert {"Flutter", "Firebase"} <= set(lost_found["skills"])
    assert portfolio["skills"][:3] == ["React", "TypeScript", "Tailwind CSS"]
    for p in (clinic, lost_found, portfolio):
        assert not any("," in b and b.count(",") >= 2 and not b.endswith(".") for b in p["bullets"])


def test_references_never_imported(draft):
    blob = repr(draft)
    for bit in REFEREE_BITS:
        assert bit not in blob, bit
    assert draft["skipped_sections"] == ["references"]
    assert draft["profile"]["email"] == "siti.contoh@example.com"  # the candidate's, not the referee's
    work = of_type(draft, "work")
    assert work[-1]["bullets"] == ["Built simple websites for 30+ clients and advised them on hosting within their budget"]


def test_wrapped_title_is_joined(draft):
    pc = of_type(draft, "work")[1]
    assert (pc["title"], pc["organization"], pc["start"], pc["end"]) == (
        "Freelance Web Designer (Part-Time)", "Self-employed", "Jan 2021", "Present")


def test_join_wrapped_rules():
    assert join_wrapped(["Freelance Web Designer (Part-", "Time) · Self-employed"]) == ["Freelance Web Designer (Part-Time) · Self-employed"]
    assert join_wrapped(["• Built a tool that", "parses logs", "• Next bullet"]) == ["• Built a tool that parses logs", "• Next bullet"]
    assert join_wrapped(["Software Intern · Kedai Tech", "Jun 2025 – Sep 2025"]) == ["Software Intern · Kedai Tech", "Jun 2025 – Sep 2025"]
    assert join_wrapped(["Ends a sentence.", "lowercase but new"]) == ["Ends a sentence.", "lowercase but new"]


def test_language_test_is_its_own_certification(draft):
    certs = of_type(draft, "certification")
    assert [c["title"] for c in certs] == ["MUET: Band 4.0", "AWS Certified Cloud Practitioner"]
    diploma = next(i for i in of_type(draft, "education") if i["title"].startswith("Diploma"))
    assert diploma["bullets"] == [] and diploma["organization"] == "Politeknik Contoh"
    assert "English" in draft["profile"]["languages"]  # MUET implies English
    assert certs[1]["end"] == "2024"


def test_education_from_layout(draft):
    p = draft["profile"]
    assert (p["education_level"], p["education_field"], p["degree_status"]) == ("Degree", "Software Engineering", "in_progress")


# ---------- import behaviour ----------

def upload(client, tmp_path, name="cv.docx"):
    lines = LAYOUT.read_text(encoding="utf-8").splitlines()
    path = make_docx(tmp_path / name, lines)
    with path.open("rb") as f:
        r = client.post("/api/resumes/parse", files={"file": (name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert r.status_code == 200, r.text
    return r.json()


def save(client, d, name, skip_duplicates=True):
    items = [{k: v for k, v in it.items() if k != "duplicate_of"} for it in d["items"]
             if not (skip_duplicates and it["duplicate_of"])]
    return client.post("/api/resumes/import", json={"name": name, "file_path": d["file_path"], "raw_text": d["raw_text"],
                                                    "profile": {}, "items": items})


def test_reupload_marks_duplicates_and_blocks_same_name(client, tmp_path):
    first = upload(client, tmp_path)
    assert all(it["duplicate_of"] is None for it in first["items"])
    assert save(client, first, "Siti Resume").status_code == 200
    n_items = len(client.get("/api/experience").json())

    second = upload(client, tmp_path, "cv2.docx")
    dup_codes = [it["duplicate_of"] for it in second["items"]]
    assert all(dup_codes) and len(set(dup_codes)) == len(dup_codes)  # every item matches a distinct bank item

    r = save(client, second, "siti resume ")  # same name, other case/space
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
    assert save(client, second, "Siti Resume v2").status_code == 200
    assert len(client.get("/api/experience").json()) == n_items  # duplicates skipped: nothing new
    # renaming onto an existing name is refused too
    resumes = client.get("/api/resumes").json()
    v2 = next(x for x in resumes if x["name"] == "Siti Resume v2")
    assert client.put(f"/api/resumes/{v2['id']}", json={"name": "Siti Resume", "item_ids": []}).status_code == 409
    assert client.post("/api/resumes", json={"name": "SITI RESUME", "item_ids": []}).status_code == 409
    # stored resume text has no referee details
    from sqlmodel import Session, select

    from app.db import engine
    from models import BaseResume
    with Session(engine) as s:
        assert all("Aminah" not in r.raw_text for r in s.exec(select(BaseResume)).all())


def test_delete_base_resume_keeps_items(client, tmp_path):
    d = upload(client, tmp_path)
    save(client, d, "To delete")
    rid = client.get("/api/resumes").json()[0]["id"]
    n = len(client.get("/api/experience").json())
    assert client.delete(f"/api/resumes/{rid}").status_code == 200
    assert client.get("/api/resumes").json() == []
    assert len(client.get("/api/experience").json()) == n


def test_clear_bank_backs_up_first(client, tmp_path):
    from app import config

    d = upload(client, tmp_path)
    save(client, d, "Siti Resume")
    before = set(config.BACKUPS_DIR.glob("*.db"))
    r = client.post("/api/experience/clear").json()
    assert r["deleted_items"] == len(d["items"]) and r["deleted_resumes"] == 1
    new_backups = set(config.BACKUPS_DIR.glob("*.db")) - before
    assert [b.name for b in new_backups] == [r["backup"]]
    assert client.get("/api/experience").json() == [] and client.get("/api/resumes").json() == []
    # codes keep counting after a clear (never reused)
    again = client.post("/api/experience", json={"type": "project", "title": "X"}).json()
    assert again["code"] == f"B{len(d['items']) + 1}"
