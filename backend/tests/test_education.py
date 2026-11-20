"""Education used for matching: highest level across bank items + profile; in progress = half points, no gate."""
from datetime import date
from pathlib import Path

import pytest

from matcher.education import EduEntry, best, field_in, from_item, level_in, progress
from resume_parser.sections import parse_resume_text
from skills.matcher import SkillMatcher
from skills.service import load_seed

TODAY = date(2026, 11, 7)
REAL = Path(__file__).parent / "fixtures" / "jobstreet_real_1.txt"


@pytest.mark.parametrize("line,level", [
    ("Bachelor of IT (Hons) Software Engineering", "Degree"),
    ("Degree", "Degree"),
    ("Diploma in Information Technology", "Diploma"),
    ("Diploma Vokasional Malaysia (DVM) Teknologi Maklumat", "Diploma"),
    ("SVM Teknologi Komputer", "SPM"),
    ("Sijil Kemahiran Malaysia (SKM) Level 3", "SPM"),
    ("Master's degree in Data Science", "Master"),
    ("Foundation in Computing", "STPM"),
    ("Universiti Contoh Malaysia", None),
])
def test_level_in(line, level):
    assert level_in(line) == level


@pytest.mark.parametrize("title,field", [
    ("Bachelor of IT (Hons) Software Engineering", "Software Engineering"),
    ("Bachelor of Computer Science (Hons)", "Computer Science"),
    ("Bachelor of Science in Computer Science", "Computer Science"),
    ("Diploma in Information Technology, Politeknik Contoh", "Information Technology"),
    ("Bachelor in IT", "Information Technology"),
    ("Degree", ""),
])
def test_field_in(title, field):
    assert field_in(title) == field


@pytest.mark.parametrize("end,text,expected", [
    ("Present", "", (True, "")),
    ("present", "expected graduation Jun 2027", (True, "2027-06-01")),
    ("", "Bachelor of IT, expected 2027", (True, "2027-06-01")),
    ("Jun 2027", "", (True, "2027-06-01")),        # future end date
    ("2021", "", (False, "")),                     # finished
    ("Sep 2026", "", (False, "")),                 # ended before today
    ("Ongoing", "", (True, "")),
])
def test_progress(end, text, expected):
    assert progress(end, text, TODAY) == expected


def test_best_prefers_highest_level_even_in_progress():
    diploma = EduEntry("Diploma", "Information Technology", False, "", "B1")
    degree = EduEntry("Degree", "Software Engineering", True, "2027-06-01", "B3")
    assert best([diploma, degree]) is degree
    # same level: completed beats in progress
    done = EduEntry("Degree", "", False, "", "profile")
    assert best([degree, done]).source == "profile"
    assert best([degree, done]).field == "Software Engineering"  # field borrowed from the same level


def test_from_item():
    e = from_item("B3", "Bachelor of IT (Hons) Software Engineering", "Universiti Contoh", "Present", [], TODAY)
    assert (e.level, e.field, e.in_progress, e.source) == ("Degree", "Software Engineering", True, "B3")


def test_parser_picks_degree_over_vocational_diploma():
    text = "\n".join([
        "Nur Contoh", "EDUCATION",
        "Diploma Vokasional Malaysia (DVM) Teknologi Maklumat | Kolej Vokasional Contoh", "2017 - 2019",
        "Bachelor of IT (Hons) Software Engineering | Universiti Contoh", "Sep 2023 - Present",
        "- Expected graduation 2027",
    ])
    p = parse_resume_text(text, SkillMatcher(load_seed()))["profile"]
    assert p["education_level"] == "Degree"
    assert p["education_field"] == "Software Engineering"
    assert p["degree_status"] == "in_progress"
    assert p["expected_graduation"] == "2027-06-01"


# ---------- the reported bug, end to end ----------

def _insurer_jd() -> str:
    from app.settings_store import default_location_map
    from sources.smart_paste import extract
    return extract(REAL.read_text(encoding="utf-8"), default_location_map()).description


def test_bank_degree_in_progress_beats_profile_diploma(client):
    """Profile says Diploma (vocational), the bank has a Degree in progress: no gate, ⚠️ half points."""
    p = client.get("/api/profile").json()
    p.update(education_level="Diploma", education_field="", degree_status="completed")
    client.put("/api/profile", json=p)
    jd = _insurer_jd()
    jid = client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Contoh Insurans",
                                                "location": "Kuala Lumpur", "description": jd}).json()["id"]
    bd = client.get(f"/api/jobs/{jid}").json()["match"]["breakdown"]
    assert "education" in [g["key"] for g in bd["gates"]]  # before: Diploma < Degree -> gate, capped at 40

    client.post("/api/experience", json={"type": "education", "title": "Bachelor of IT (Hons) Software Engineering",
                                         "organization": "Universiti Contoh", "start": "Sep 2023", "end": "Present"})
    bd = client.get(f"/api/jobs/{jid}").json()["match"]["breakdown"]
    edu = next(c for c in bd["categories"] if c["key"] == "education")
    assert not bd["gates"]
    assert edu["status"] == "partial" and edu["points"] == 5
    assert "Degree (in progress" in edu["note"] and "from B1" in edu["note"]
    field = next(i for i in edu["items"] if i["name"].startswith("Field"))
    assert field["status"] == "met" and "Software Engineering" in field["detail"]
    assert bd["total"] > 40


def test_profile_status_lists_missing_fields(client):
    s = client.get("/api/profile/status").json()
    assert s["education"] is None
    assert [m["key"] for m in s["missing"]] == ["education_level", "preferred_locations", "years_of_experience"]

    client.post("/api/experience", json={"type": "education", "title": "Degree", "organization": "Universiti Contoh",
                                         "end": "Present"})
    s = client.get("/api/profile/status").json()
    assert s["education"]["level"] == "Degree" and s["education"]["in_progress"] is True
    assert [m["key"] for m in s["missing"]] == ["education_field", "preferred_locations", "years_of_experience"]

    p = client.get("/api/profile").json()
    p.update(education_field="Software Engineering", preferred_locations=["Selangor"], years_confirmed=True)
    client.put("/api/profile", json=p)
    s = client.get("/api/profile/status").json()
    assert s["missing"] == [] and s["education"]["field"] == "Software Engineering"


def test_migration_adds_years_confirmed(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine, text

    from app import migrations

    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE profile (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL)")
    con.execute("INSERT INTO profile (name) VALUES ('Me')")
    con.commit()
    con.close()
    eng = create_engine(f"sqlite:///{db}")
    assert migrations.run(eng) == ["profile.years_confirmed", "profile.linkedin_url", "profile.github_url",
                                   "profile.portfolio_url"]
    with eng.connect() as c:
        rows = c.execute(text("SELECT name, years_confirmed, linkedin_url, github_url, portfolio_url FROM profile")).all()
        assert rows == [("Me", 0, "", "", "")]
    assert migrations.run(eng) == []  # only once
    eng.dispose()


def test_parser_splits_qualification_without_organization():
    text = "EDUCATION\nSVM Teknologi Komputer\n2016\nDegree in Computer Science\n2023 - Present"
    items = parse_resume_text(text, SkillMatcher(load_seed()))["items"]
    assert [i["title"] for i in items] == ["SVM Teknologi Komputer", "Degree in Computer Science"]
