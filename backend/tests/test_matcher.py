"""Matcher tests against realistic (fake) JDs in tests/fixtures/jds."""
from pathlib import Path

import pytest

from matcher.jd_sections import split_clauses
from matcher.rules import extract_education, extract_languages, extract_years
from matcher.scoring import Candidate, ScoringConfig, score_job
from skills.matcher import SkillMatcher
from skills.service import load_seed

JDS = Path(__file__).parent / "fixtures" / "jds"


def jd(name: str) -> str:
    return (JDS / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matcher() -> SkillMatcher:
    return SkillMatcher(load_seed())


@pytest.fixture
def me() -> Candidate:
    """A fake fresh-grad SE student."""
    return Candidate(
        years=0,
        education_level="Degree",
        education_field="Software Engineering",
        degree_status="completed",
        languages=["English", "BM"],
        preferred_locations=["Kuala Lumpur", "Selangor", "Remote"],
        remote_ok=True,
        skill_evidence={
            "Python": ["B1"], "Django": ["B1"], "JavaScript": ["B2"], "React": ["B2"],
            "HTML": ["B2"], "CSS": ["B2"], "Git": ["profile"], "SQL": ["B3"], "Java": ["B4"],
            "REST API": ["B1"], "Problem Solving": ["profile"], "Communication": ["profile"],
        },
    )


def cat(result, key):
    return next(c for c in result["categories"] if c["key"] == key)


# ---------- clause classification ----------

def test_sections_and_phrases():
    kinds = {c.text: c.kind for c in split_clauses(jd("junior_react"))}
    assert kinds["Familiar with Git"] == "required"
    assert kinds["Experience with Next.js"] == "preferred"
    assert kinds["Medical insurance, free parking, AWS certification sponsorship"] == "ignored"
    assert all(k == "ignored" for t, k in kinds.items() if "Python workshops" in t)


def test_inline_headings():
    clauses = split_clauses(jd("inline_headings"))
    pref = [c.text for c in clauses if c.kind == "preferred"]
    assert any("Kotlin" in t for t in pref)
    assert any("Java, SQL, Git" in c.text and c.kind == "required" for c in clauses)


@pytest.mark.parametrize("heading", ["Responsibilities", "Key Responsibilities:", "Job Duties",
                                     "What you'll do", "Roles & Responsibilities", "Duties and responsibilities"])
def test_responsibilities_sections_are_preferred(heading, matcher):
    text = f"{heading}\n- Build APIs in Go\n- Must maintain Kubernetes clusters\n\nRequirements\n- Python"
    kinds = {c.text: c.kind for c in split_clauses(text)}
    assert kinds["Build APIs in Go"] == "preferred"
    assert kinds["Must maintain Kubernetes clusters"] == "preferred"  # section wins over "must"
    assert kinds["Python"] == "required"
    me = Candidate(skill_evidence={"Python": ["B1"]})
    r = score_job(text, "", me, matcher)
    assert r["required_skills"] == ["Python"]
    assert set(r["preferred_skills"]) == {"Go", "Kubernetes"}


def test_phrase_overrides_required_section():
    clauses = split_clauses(jd("masters_data"))
    bm = next(c for c in clauses if "Bahasa" in c.text)
    assert bm.kind == "preferred"


def test_no_headings_defaults_to_required():
    clauses = split_clauses(jd("no_headings"))
    assert any("Node.js" in c.text and c.kind == "required" for c in clauses)
    assert any("Docker" in c.text and c.kind == "preferred" for c in clauses)


# ---------- rules ----------

@pytest.mark.parametrize("text,years", [
    ("3+ years of experience in Java", 3),
    ("Minimum 2 years working experience", 2),
    ("At least 1 year of experience", 1),
    ("2-3 years of relevant experience", 2),
    ("1 to 3 years experience in web development", 1),
    ("two (2) years of experience", 2),
    ("Requires 5 yrs experience", 5),
])
def test_years_patterns(text, years):
    assert extract_years(split_clauses(text)).years == years


def test_years_ignores_company_history():
    # "20 years ago" / "30 years of combined experience" sit under "About the company".
    assert extract_years(split_clauses(jd("masters_data"))).years == 3


def test_years_not_specified():
    assert extract_years(split_clauses("Requirements:\n- Python\n- SQL")).years is None


def test_fresh_grad_means_zero_years():
    r = extract_years(split_clauses(jd("junior_react")))
    assert r.years == 0 and r.fresh_grad_ok


def test_education_lowest_level():
    e = extract_education(split_clauses(jd("inline_headings")))
    assert e.level == "Diploma" and e.mandatory
    e = extract_education(split_clauses(jd("masters_data")))
    assert e.level == "Master" and "statistics" in e.fields


def test_languages_with_context():
    langs = {l.language: l.mandatory for l in extract_languages(split_clauses(jd("mandarin_support")))}
    assert langs == {"Mandarin": True, "Bahasa Malaysia": True, "English": True}
    # "Chinese New Year" in About Us must not become a language requirement.
    assert extract_languages(split_clauses(jd("junior_react"))) == [] or all(
        l.language == "English" for l in extract_languages(split_clauses(jd("junior_react"))))


# ---------- full scoring ----------

def test_junior_react_high_score(me, matcher):
    r = score_job(jd("junior_react"), "Kuala Lumpur", me, matcher)
    req = cat(r, "required_skills")
    assert {i["name"] for i in req["items"]} == {"JavaScript", "HTML", "CSS", "Git"}
    # React / TypeScript only appear under "Job Responsibilities" -> preferred
    assert {"React", "TypeScript"} <= set(r["preferred_skills"])
    assert "AWS" not in r["required_skills"] + r["preferred_skills"]  # from Benefits
    assert "Python" not in r["required_skills"]  # from About Us
    assert cat(r, "years")["status"] == "met"
    assert cat(r, "education")["status"] == "met"
    assert not r["gates"]
    assert r["total"] >= 70


def test_senior_java_gated(me, matcher):
    r = score_job(jd("senior_java"), "Kuala Lumpur", me, matcher)
    assert [g["key"] for g in r["gates"]] == ["years"]
    assert cat(r, "years")["status"] == "not_met"
    assert r["total"] <= 40


def test_mandatory_language_gate(me, matcher):
    r = score_job(jd("mandarin_support"), "Penang", me, matcher)
    keys = [g["key"] for g in r["gates"]]
    assert "language" in keys
    assert r["total"] <= 40
    loc = next(i for i in cat(r, "language_location")["items"] if i["name"].startswith("Location"))
    assert loc["status"] == "not_met"


def test_remote_job_location_met(me, matcher):
    r = score_job(jd("fresh_grad_python"), "Remote", me, matcher)
    assert "Docker" in r["preferred_skills"] and "AWS" in r["preferred_skills"]
    # "What you'll do" is a responsibilities section -> its skills are preferred
    assert {"Django", "REST API", "SQL"} <= set(r["preferred_skills"])
    # Python is also in the job title line (no heading -> required), and required wins.
    # Problem Solving is a soft skill: listed separately, not scored.
    assert r["required_skills"] == ["Python"]
    assert [x["name"] for x in r["soft_skills"]] == ["Problem Solving"]
    assert cat(r, "required_skills")["status"] == "met"
    assert cat(r, "preferred_skills")["status"] == "partial"
    loc = next(i for i in cat(r, "language_location")["items"] if i["name"].startswith("Location"))
    assert loc["status"] == "met"
    assert r["total"] >= 80


def test_partial_years(me, matcher):
    me.years = 1
    r = score_job(jd("no_headings"), "", me, matcher)
    y = cat(r, "years")
    assert y["status"] == "partial" and y["points"] == 10
    assert not r["gates"]


def test_two_years_short_is_gate(me, matcher):
    r = score_job(jd("no_headings"), "", me, matcher)
    assert [g["key"] for g in r["gates"]] == ["years"]


def test_not_specified_gets_full_points(me, matcher):
    r = score_job(jd("no_headings"), "", me, matcher)
    for key in ("education",):
        c = cat(r, key)
        assert c["not_specified"] and c["points"] == c["max"]


def test_degree_in_progress_is_partial(me, matcher):
    me.degree_status = "in_progress"
    me.expected_graduation = "2027-06"
    r = score_job(jd("junior_react"), "Kuala Lumpur", me, matcher)
    e = cat(r, "education")
    assert e["status"] == "partial" and e["points"] == 5
    assert "in progress" in e["note"] and "2027-06" in e["note"]
    assert not r["gates"]


def test_missing_mandatory_degree_is_gate(me, matcher):
    me.education_level = "Diploma"
    r = score_job(jd("masters_data"), "Kuala Lumpur", me, matcher)
    assert "education" in [g["key"] for g in r["gates"]]


def test_field_mismatch_halves_education(me, matcher):
    me.education_field = "Accounting"
    r = score_job(jd("junior_react"), "Kuala Lumpur", me, matcher)
    assert cat(r, "education")["points"] == 5


def test_preferred_language_missing_is_not_gate(me, matcher):
    me.languages = ["English"]
    me.years = 5
    me.education_level = "Master"
    r = score_job(jd("masters_data"), "Kuala Lumpur", me, matcher)
    assert "language" not in [g["key"] for g in r["gates"]]


def test_breakdown_points_add_up(me, matcher):
    for name in ("junior_react", "senior_java", "fresh_grad_python", "inline_headings"):
        r = score_job(jd(name), "Cyberjaya", me, matcher)
        assert sum(c["max"] for c in r["categories"]) == 100
        assert round(sum(c["points"] for c in r["categories"]), 1) == r["raw_total"]
        if not r["gates"]:
            assert r["total"] == round(r["raw_total"])


def test_custom_weights_and_cap(me, matcher):
    cfg = ScoringConfig.model_validate({"weights": {"required_skills": 90, "preferred_skills": 10, "years": 0,
                                                   "education": 0, "language_location": 0},
                                        "gates": {"cap": 20}})
    r = score_job(jd("senior_java"), "", me, matcher, cfg)
    assert r["total"] <= 20


def test_each_item_has_status(me, matcher):
    r = score_job(jd("mandarin_support"), "Penang", me, matcher)
    for c in r["categories"]:
        assert c["status"] in {"met", "partial", "not_met", "not_specified"}
        for i in c["items"]:
            assert i["status"] in {"met", "partial", "not_met", "not_specified"}
