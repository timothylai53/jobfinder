import pytest

from resume_parser.extract_text import UnsupportedFile, extract_text
from resume_parser.sections import parse_resume_text
from skills.matcher import SkillMatcher
from skills.service import load_seed
from tests.fixtures.make_files import FAKE_RESUME_LINES, make_docx, make_pdf


@pytest.fixture(scope="module")
def matcher():
    return SkillMatcher(load_seed())


def by_type(items, t):
    return [i for i in items if i["type"] == t]


def check_draft(draft):
    p = draft["profile"]
    assert p["name"] == "Aisyah Tan"
    assert p["email"] == "aisyah.tan@example.com"
    assert "12-345 6789" in p["phone"]
    assert p["location"] == "Petaling Jaya, Selangor"
    assert p["education_level"] == "Degree"
    assert p["degree_status"] == "in_progress"
    assert p["expected_graduation"] == "2027-06-01"
    assert p["languages"] == ["English", "Bahasa Malaysia", "Mandarin"]
    assert {"Python", "Java", "JavaScript", "React", "SQL", "Git", "Docker"} <= set(p["skills"])

    items = draft["items"]
    work = by_type(items, "work")
    assert len(work) == 1
    assert work[0]["title"] == "Software Engineering Intern"
    assert work[0]["organization"] == "Kedai Tech Sdn Bhd"
    assert (work[0]["start"], work[0]["end"]) == ("Jun 2025", "Sep 2025")
    assert len(work[0]["bullets"]) == 2
    assert {"React", "TypeScript", "Python", "FastAPI", "PostgreSQL", "REST API"} <= set(work[0]["skills"])

    proj = by_type(items, "project")
    assert len(proj) == 1 and proj[0]["title"] == "Campus Food Ordering App"
    assert {"Flutter", "Firebase", "Scrum"} <= set(proj[0]["skills"])

    edu = by_type(items, "education")
    assert len(edu) == 1 and edu[0]["organization"] == "Universiti Contoh Malaysia"
    assert edu[0]["end"] == "Present"


def test_parse_plain_text(matcher):
    check_draft(parse_resume_text("\n".join(FAKE_RESUME_LINES), matcher))


def test_parse_docx(tmp_path, matcher):
    text = extract_text(make_docx(tmp_path / "cv.docx"))
    check_draft(parse_resume_text(text, matcher))


def test_parse_pdf(tmp_path, matcher):
    text = extract_text(make_pdf(tmp_path / "cv.pdf"))
    assert "Kedai Tech" in text
    check_draft(parse_resume_text(text, matcher))


def test_unsupported_file(tmp_path):
    p = tmp_path / "cv.txt"
    p.write_text("hi")
    with pytest.raises(UnsupportedFile):
        extract_text(p)


def test_bullets_without_header_and_wrapped_lines(matcher):
    text = "PROJECTS\n• Built a CLI tool in Rust that\nparses logs quickly\n• Second bullet"
    items = parse_resume_text(text, matcher)["items"]
    assert len(items) == 1
    assert items[0]["bullets"] == ["Built a CLI tool in Rust that parses logs quickly", "Second bullet"]
    assert "Rust" in items[0]["skills"]


def test_completed_degree(matcher):
    text = "EDUCATION\nDiploma in Information Technology, Politeknik Contoh\n2018 - 2021"
    p = parse_resume_text(text, matcher)["profile"]
    assert p["education_level"] == "Diploma"
    assert p["education_field"] == "Information Technology"
    assert p["degree_status"] == "completed"


def test_unparsed_lines_flag_what_was_not_imported(matcher):
    text = "\n".join(FAKE_RESUME_LINES) + "\nREFERENCES\nAvailable on request\nSKILLS\nBasket weaving"
    draft = parse_resume_text(text, matcher)
    lines = {u["line"]: u["reason"] for u in draft["unparsed_lines"]}
    assert lines == {
        "Final-year Software Engineering student who enjoys building web apps.": "summary is not imported",
        "Basket weaving": "no known skills found",
    }
    # the References section is removed entirely, not listed
    assert draft["skipped_sections"] == ["references"] and "Available on request" not in draft["raw_text"]
