"""After the LinkedIn smoke test and the Draughtman/QA/SRE review: entry-level default keywords, "Version control"
no longer means Git, duties-only ads count their skills as required, thin evidence is low confidence. No network."""
from sqlmodel import Session, select

from matcher.scoring import Candidate, score_job
from models import SearchProfile, Skill
from skills.matcher import SkillDef, SkillMatcher
from skills.service import load_seed, remove_retired_aliases
from sources.health import DEFAULT_KEYWORDS, update_default_keywords

MATCHER = SkillMatcher(load_seed())
ME = Candidate(years=0, skill_evidence={"Python": ["B1"], "SQL": ["B1"], "Git": ["B2"], "Docker": ["B2"]})


def _engine():
    from app.db import engine
    return engine


# ---------- 1. keywords ----------

def test_new_default_keywords_and_old_profiles_updated(client):
    assert DEFAULT_KEYWORDS == ["junior software engineer", "graduate software engineer", "software developer",
                                "fresh graduate IT"]
    with Session(_engine()) as s:
        profiles = {p.name: p for p in s.exec(select(SearchProfile)).all()}
        assert profiles["KL/Selangor"].keywords == DEFAULT_KEYWORDS  # fresh database: new defaults
        # an older database: default profiles on the old list, my own profiles untouched
        profiles["KL/Selangor"].keywords = ["software engineer", "software developer", "full stack developer"]
        profiles["Sabah"].keywords = ["my own keyword"]
        s.add(SearchProfile(name="Smoke test", keywords=["software engineer", "software developer", "full stack developer"],
                            locations=["Kuala Lumpur"]))
        s.commit()
        assert update_default_keywords(s) == 1
        s.commit()
        got = {p.name: p.keywords for p in s.exec(select(SearchProfile)).all()}
        assert got["KL/Selangor"] == DEFAULT_KEYWORDS
        assert got["Sabah"] == ["my own keyword"]
        assert got["Smoke test"] == ["software engineer", "software developer", "full stack developer"]
        assert update_default_keywords(s) == 0  # idempotent


# ---------- 2. Git alias ----------

def test_version_control_is_not_git():
    jd = "Requirements:\n- Maintain proper records, version control and documentation for all drawings"
    assert "Git" not in score_job(jd, "", ME, MATCHER)["required_skills"]
    assert "Git" in score_job("Requirements:\n- Git and GitHub", "", ME, MATCHER)["required_skills"]


def test_retired_alias_removed_from_existing_dictionary(client):
    with Session(_engine()) as s:
        git = s.exec(select(Skill).where(Skill.name == "Git")).one()
        git.aliases = [*git.aliases, "Version control"]  # an older database
        s.commit()
        assert remove_retired_aliases(s) == 1 and remove_retired_aliases(s) == 0
        assert "Version control" not in s.exec(select(Skill).where(Skill.name == "Git")).one().aliases


# ---------- 3. no requirements section ----------

DUTIES_ONLY = """Responsibilities
- Build test plans and automate regression tests in Python
- Maintain SQL test data and Docker environments
- Work with developers on Git workflows
- Experience with Kubernetes is a plus"""


def test_duties_only_ad_counts_skills_as_required():
    r = score_job(DUTIES_ONLY, "", ME, MATCHER)
    assert set(r["required_skills"]) == {"Python", "SQL", "Docker", "Git"}
    assert r["preferred_skills"] == ["Kubernetes"]  # an explicit "is a plus" stays preferred
    req = next(c for c in r["categories"] if c["key"] == "required_skills")
    assert not req["not_specified"] and req["points"] == 45


def test_ad_with_requirements_section_keeps_duties_preferred():
    jd = DUTIES_ONLY + "\nRequirements\n- Degree in Computer Science\n- Java"
    r = score_job(jd, "", ME, MATCHER)
    assert r["required_skills"] == ["Java"]
    assert {"Python", "SQL", "Docker", "Git"} <= set(r["preferred_skills"])


def test_generic_job_description_heading_is_not_a_requirements_section():
    """The SRE II shape: 'Job description' (no skills) + 'What you will do' (skills) + 'Bonus points'."""
    jd = ("Job description\nWe are hiring an engineer to join our platform team.\n"
          "What you will do\n- Automate infrastructure with Python and Docker\n- Write SQL reports\n"
          "Bonus points\n- Kubernetes\n- Terraform")
    r = score_job(jd, "", ME, MATCHER)
    assert set(r["required_skills"]) == {"Python", "Docker", "SQL"}
    assert set(r["preferred_skills"]) == {"Kubernetes", "Terraform"}  # the bonus section stays preferred


def test_duties_only_with_missing_skills_no_longer_gets_free_required_points():
    jd = "Responsibilities\n- Develop services in Go and Rust\n- Deploy on Kubernetes"
    req = next(c for c in score_job(jd, "", ME, MATCHER)["categories"] if c["key"] == "required_skills")
    assert req["points"] == 0  # before: 45 for an "empty" required list


# ---------- 4. thin evidence ----------

def test_thin_evidence_is_low_confidence_and_capped():
    r = score_job("Requirements:\n- Git", "", ME, MATCHER)
    assert r["low_confidence"].startswith("Thin evidence: only 1 skill(s) found (Git)")
    assert r["total"] == 50


def test_two_skills_plus_anything_stated_is_normal():
    r = score_job("Requirements:\n- Python\n- SQL\n- Fresh graduates welcome", "", ME, MATCHER)
    assert r["low_confidence"] == "" and r["total"] == 100


def test_three_skills_is_not_thin():
    r = score_job("Requirements:\n- Python\n- SQL\n- Docker", "", ME, MATCHER)
    assert r["low_confidence"] == "" and r["total"] == 100


def test_custom_matcher_still_works():
    m = SkillMatcher([SkillDef(name="Cobol", aliases=[], category="language")])
    assert score_job("Requirements:\n- Cobol", "", Candidate(), m)["low_confidence"].startswith("Thin evidence")
