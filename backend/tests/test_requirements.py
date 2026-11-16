"""'One of these' skill groups and soft skills (listed, not scored)."""
from pathlib import Path

import pytest

from app.settings_store import default_location_map
from matcher.requirements import from_clause
from matcher.scoring import Candidate, ScoringConfig, score_job
from skills.matcher import SkillMatcher
from skills.service import load_seed
from sources.smart_paste import extract

REAL = Path(__file__).parent / "fixtures" / "jobstreet_real_1.txt"
MAP = default_location_map()


@pytest.fixture(scope="module")
def m() -> SkillMatcher:
    return SkillMatcher(load_seed())


def groups(text, m, soft=False):
    return [(r.skills, r.equivalent_ok) for r in from_clause(text, m, soft).hard]


# ---------- grouping ----------

def test_slashes_with_or_equivalent(m):
    assert groups("Must be proficient in at least one (1) programming language. (C#/ Java/ Javascript or equivalent)", m) == [
        (["C#", "Java", "JavaScript"], True)]


def test_or_and_comma_or(m):
    assert groups("Experience with Java, Python or Go", m) == [(["Java", "Python", "Go"], False)]
    assert groups("React or Vue.js", m) == [(["React", "Vue.js"], False)]


def test_at_least_one_of_applies_to_the_following_list(m):
    assert groups("Hands-on with at least one of AWS, Azure, GCP", m) == [(["AWS", "Microsoft Azure", "Google Cloud"], False)]
    assert groups("Any of the following: Jest, Cypress, Playwright", m) == [(["Jest", "Cypress", "Playwright"], False)]


def test_plain_lists_stay_separate(m):
    assert groups("Solid understanding of JavaScript, HTML and CSS", m) == [
        (["JavaScript"], False), (["HTML"], False), (["CSS"], False)]
    # "at least one" earlier in the sentence does not turn a later plain list into alternatives
    assert groups("At least one year of experience; Python, Django", m) == [(["Python"], False), (["Django"], False)]


def test_or_equivalent_on_a_single_skill(m):
    assert groups("Knowledge of Jira or equivalent", m) == [(["Jira"], True)]


def test_soft_skills_are_split_out(m):
    out = from_clause("Must have strong analytical, problem-solving, good communication and stakeholder management skills.", m)
    assert out.hard == []
    assert out.soft == ["Problem Solving", "Communication", "Stakeholder Management"]
    out = from_clause("Python and teamwork", m, score_soft=True)
    assert [r.skills for r in out.hard] == [["Python"], ["Teamwork"]] and out.soft == []


# ---------- scoring on the real-format insurance job ----------

def insurer(cand, cfg=None, m=None):
    d = extract(REAL.read_text(encoding="utf-8"), MAP)
    return score_job(d.description, d.location, cand, m or SkillMatcher(load_seed()), cfg)


def items(r, key):
    return {i["name"]: i for c in r["categories"] if c["key"] == key for i in c["items"]}


def test_insurer_groups_met_with_java_and_sql(m):
    me = Candidate(skill_evidence={"Java": ["B2"], "SQL": ["profile"]}, preferred_locations=["Kuala Lumpur"], location_map=MAP)
    r = insurer(me, m=m)
    req = items(r, "required_skills")
    lang = req["One of: C# / Java / JavaScript (or equivalent)"]
    assert lang["status"] == "met" and lang["detail"] == "Java, from B2" and lang["group"] == ["C#", "Java", "JavaScript"]
    sql_group = req["One of: Microsoft SQL Server / MySQL (or equivalent)"]
    assert sql_group["status"] == "met" and sql_group["detail"] == "equivalent: SQL, from profile"
    assert req["SQL"]["status"] == "met"
    assert req["SDLC"]["status"] == "not_met"
    cat = next(c for c in r["categories"] if c["key"] == "required_skills")
    assert cat["note"] == "3 of 4 matched" and cat["points"] == 33.8


def test_group_without_equivalent_needs_a_listed_skill(m):
    jd = "Requirements\n- Proficient in C#/ Java"
    r = score_job(jd, "", Candidate(skill_evidence={"Python": ["B1"]}), m)
    g = items(r, "required_skills")["One of: C# / Java"]
    assert g["status"] == "not_met" and g["detail"] == "none of these in Experience Bank or profile"


def test_soft_skills_listed_but_not_scored_by_default(m):
    me = Candidate(skill_evidence={"Java": ["B2"], "SQL": ["profile"], "Communication": ["profile"]})
    r = insurer(me, m=m)
    soft = {s["name"]: s for s in r["soft_skills"]}
    assert set(soft) == {"Problem Solving", "Communication", "Stakeholder Management"}
    assert soft["Communication"]["status"] == "met" and soft["Problem Solving"]["status"] == "not_met"
    assert not any(n in items(r, "required_skills") for n in soft)


def test_score_soft_skills_toggle(m):
    me = Candidate(skill_evidence={"Java": ["B2"], "SQL": ["profile"]})
    off = insurer(me, m=m)
    on = insurer(me, ScoringConfig(score_soft_skills=True), m=m)
    assert on["soft_skills"] == []
    assert {"Communication", "Problem Solving", "Stakeholder Management"} <= set(items(on, "required_skills"))
    req_on = next(c for c in on["categories"] if c["key"] == "required_skills")
    req_off = next(c for c in off["categories"] if c["key"] == "required_skills")
    assert req_on["points"] < req_off["points"]  # three unmet soft skills now cost points


# ---------- persistence ----------

def test_settings_toggle_round_trip_rescores(client):
    jid = client.post("/api/jobs/manual", json={"title": "Dev", "description": "Requirements:\n- Python\n- Teamwork"}).json()["id"]
    names = lambda: [i["name"] for c in client.get(f"/api/jobs/{jid}").json()["match"]["breakdown"]["categories"]
                     if c["key"] == "required_skills" for i in c["items"]]
    assert names() == ["Python"]
    s = client.get("/api/settings").json()
    assert s["scoring"]["score_soft_skills"] is False
    s["scoring"]["score_soft_skills"] = True
    client.put("/api/settings", json={"scoring": s["scoring"], "general": s["general"]})
    assert names() == ["Python", "Teamwork"]


def test_new_seed_skills_added_once_never_readded(client):
    from sqlmodel import Session, select

    from app.db import engine
    from models import AppSetting, Skill
    from skills.service import SEED_VERSION_KEY, seed_if_empty

    with Session(engine) as s:
        # simulate an older install: version 1, without the skills added in version 2
        for sk in s.exec(select(Skill).where(Skill.name.in_(["Stakeholder Management", "Interpersonal Skills"]))).all():
            s.delete(sk)
        s.get(AppSetting, SEED_VERSION_KEY).value = 1
        s.commit()
        assert seed_if_empty(s) == 2
        sh = s.exec(select(Skill).where(Skill.name == "Stakeholder Management")).one()
        assert sh.category == "soft"
        s.delete(sh)  # I delete it myself...
        s.commit()
        assert seed_if_empty(s) == 0  # ...and it stays deleted
        assert s.exec(select(Skill).where(Skill.name == "Stakeholder Management")).first() is None


def test_equivalent_stays_within_family(m):
    jd = "Requirements\n- Must be proficient in SQL & Relational Database (MS SQL / MySQL or equivalent)"
    g = lambda ev: items(score_job(jd, "", Candidate(skill_evidence=ev), m), "required_skills")[
        "One of: Microsoft SQL Server / MySQL (or equivalent)"]
    assert g({"PostgreSQL": ["B2"]})["detail"] == "equivalent: PostgreSQL, from B2"
    assert g({"Firebase": ["B3"], "MongoDB": ["B1"]})["status"] == "not_met"  # NoSQL is not equivalent to MySQL
    # languages have no family: any language counts for "C#/ Java or equivalent"
    jd2 = "Requirements\n- C#/ Java or equivalent"
    r = score_job(jd2, "", Candidate(skill_evidence={"Python": ["B1"]}), m)
    assert items(r, "required_skills")["One of: C# / Java (or equivalent)"]["detail"] == "equivalent: Python, from B1"
