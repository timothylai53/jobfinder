from sqlmodel import Session, select

from filters.engine import JobView, Rule, evaluate
from models import FilterRule, Job

TITLE_ALLOW_LIST = ("software, developer, engineer, programmer, full stack, frontend, backend, web, IT, system, data, "
                    "QA, test")
DEFAULT_RULES = [
    FilterRule(type="title_contains", value="Senior, Lead, Manager, Principal, Head of", enabled=True),
    FilterRule(type="min_years_over", value="3", enabled=True),
    FilterRule(type="title_must_contain_one_of", value=TITLE_ALLOW_LIST, enabled=False),  # off until I turn it on
]


def seed_if_empty(session: Session) -> None:
    if session.exec(select(FilterRule.id).limit(1)).first() is None:
        for r in DEFAULT_RULES:
            session.add(FilterRule(**r.model_dump(exclude={"id"})))
        session.commit()
        return
    # Rule types added in later versions are seeded once (disabled defaults don't change anything)
    have = set(session.exec(select(FilterRule.type)).all())
    for r in DEFAULT_RULES:
        if r.type not in have and not r.enabled:
            session.add(FilterRule(**r.model_dump(exclude={"id"})))
    session.commit()


def load_rules(session: Session) -> list[Rule]:
    return [Rule(r.id, r.type, r.value, r.enabled) for r in session.exec(select(FilterRule)).all()]


def apply_to_job(job: Job, rules: list[Rule]) -> None:
    """Hide/unhide by rules. Manually hidden jobs are left alone."""
    if job.hidden_by == "manual":
        return
    reason = evaluate(rules, JobView(job.title, job.company, job.description, job.salary_min, job.salary_max))
    job.hidden = reason is not None
    job.hidden_reason = reason or ""
    job.hidden_by = "rule" if reason else ""


def reapply_all(session: Session) -> int:
    rules = load_rules(session)
    jobs = session.exec(select(Job)).all()
    for j in jobs:
        apply_to_job(j, rules)
    session.commit()
    return sum(j.hidden for j in jobs)
