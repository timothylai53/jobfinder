"""Glue between DB rows and the pure scoring function."""
from datetime import date

from sqlmodel import Session, col, select

from app.settings_store import get_location_map, get_scoring
from matcher import education
from matcher.scoring import Candidate, score_job
from models import ExperienceItem, Job, MatchResult, Profile
from models._base import require_id
from skills.matcher import SkillMatcher
from skills.service import build_matcher


def get_profile(session: Session) -> Profile:
    p = session.get(Profile, 1)
    if p is None:
        p = Profile(id=1)
        session.add(p)
        session.commit()
        session.refresh(p)
    return p


def effective_education(session: Session, profile: Profile | None = None) -> education.EduEntry | None:
    """Highest qualification across Experience Bank education/certification items and the Profile."""
    p = profile or get_profile(session)
    entries = []
    for it in session.exec(select(ExperienceItem).where(col(ExperienceItem.type).in_(["education", "certification"]))).all():
        e = education.from_item(it.code, it.title, it.organization, it.end, list(it.bullets))
        if e:
            entries.append(e)
    if p.education_level:
        in_prog = p.degree_status == "in_progress"
        entries.append(education.EduEntry(p.education_level, p.education_field, in_prog,
                                          p.expected_graduation.isoformat() if in_prog and p.expected_graduation else "",
                                          "profile"))
    top = education.best(entries)
    if top and not top.field and p.education_field and (not p.education_level or p.education_level == top.level):
        top.field = p.education_field  # field typed in the Profile for this same level
    return top


def _month_year(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%b %Y")
    except ValueError:
        return ""


def build_candidate(session: Session, matcher: SkillMatcher) -> Candidate:
    p = get_profile(session)
    evidence: dict[str, list[str]] = {}

    def add(skill: str, src: str):
        lst = evidence.setdefault(skill, [])
        if src not in lst:
            lst.append(src)

    for item in session.exec(select(ExperienceItem).order_by(col(ExperienceItem.id))).all():
        linked = matcher.normalize_list(list(item.skills))
        found = matcher.find(" ".join([item.title, *item.bullets]))
        for s in dict.fromkeys(linked + found):
            add(s, item.code)
    for s in matcher.normalize_list(list(p.skills)):
        add(s, "profile")
    edu = effective_education(session, p)
    return Candidate(
        years=p.years_of_experience or 0,
        education_level=edu.level if edu else "",
        education_field=edu.field if edu else "",
        degree_status="in_progress" if edu and edu.in_progress else "completed",
        expected_graduation=_month_year(edu.expected) if edu and edu.expected else "",
        education_source=edu.source if edu else "",
        languages=list(p.languages),
        preferred_locations=list(p.preferred_locations),
        location_map=get_location_map(session),
        remote_ok=p.remote_ok,
        skill_evidence=evidence,
    )


class Scorer:
    """Loads the dictionary, candidate and config once, then scores many jobs."""

    def __init__(self, session: Session):
        self.session = session
        self.matcher = build_matcher(session)
        self.candidate = build_candidate(session, self.matcher)
        self.config = get_scoring(session)

    def score(self, job: Job) -> MatchResult:
        location = job.location
        if job.work_arrangement.lower() == "remote" and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()
        r = score_job(job.description, location, self.candidate, self.matcher, self.config)
        old = self.session.exec(select(MatchResult).where(MatchResult.job_id == job.id, MatchResult.method == "quick")).all()
        for o in old:
            self.session.delete(o)
        mr = MatchResult(job_id=require_id(job), total=r["total"], breakdown=r,
                         gate_flags=[g["key"] for g in r["gates"]], method="quick")
        self.session.add(mr)
        return mr


def rescore_all(session: Session) -> int:
    scorer = Scorer(session)
    jobs = session.exec(select(Job)).all()
    for j in jobs:
        scorer.score(j)
    session.commit()
    return len(jobs)
