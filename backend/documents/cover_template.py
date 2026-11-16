"""Cover letter template mode (brief §6.6): fill-in-the-blanks from the job, my top 3 matched skills and 1-2
chosen bank items. Works with AI off. Everything in it comes from the job, my bank or my profile."""
import re

from sqlmodel import Session, select

from matcher.service import effective_education, get_profile
from models import ExperienceItem, Job, MatchResult

TYPE_WORD = {"work": "role", "project": "project", "achievement": "achievement", "education": "studies",
             "certification": "certification", "publication": "publication"}


def matched_skills(session: Session, job: Job, limit: int = 3) -> list[str]:
    """Skills the quick score found met: required first, then preferred."""
    mr = session.exec(select(MatchResult).where(MatchResult.job_id == job.id, MatchResult.method == "quick")).first()
    if mr is None:
        return []
    out: list[str] = []
    for key in ("required_skills", "preferred_skills"):
        cat = next((c for c in mr.breakdown.get("categories", []) if c["key"] == key), None)
        for it in (cat or {}).get("items", []):
            if it.get("status") == "met":
                for name in (it.get("group") or [it["name"].replace(" (or equivalent)", "")]):
                    if name not in out and not name.startswith("One of:"):
                        out.append(name)
    return out[:limit]


def suggest_items(session: Session, job: Job, limit: int = 2) -> list[str]:
    """Bank items (work/project first) whose skills overlap the job's matched skills the most."""
    skills = {s.lower() for s in matched_skills(session, job, limit=10)}
    items = session.exec(select(ExperienceItem).where(ExperienceItem.type.in_(["work", "project", "achievement"]))).all()

    def overlap(it: ExperienceItem) -> int:
        text = " ".join([it.title, *it.bullets, *it.skills]).lower()
        return sum(1 for s in skills if s in text)

    ranked = sorted(items, key=lambda it: (-overlap(it), it.type != "work", it.id))
    return [it.code for it in ranked[:limit]]


_PAST_VERB = re.compile(r"^(?:[A-Z][a-z]+ed|Built|Led|Wrote|Ran|Made|Taught|Won|Set|Drove|Brought|Sought|Kept|Held)\b")


def item_sentence(item: ExperienceItem) -> str:
    """'In my project “X” at Org, I built ...' from the item's first bullet, word for word."""
    where = f"In my {TYPE_WORD.get(item.type, 'experience')} “{item.title}”" + (f" at {item.organization}" if item.organization else "")
    if not item.bullets:
        return f"{where}, I gained hands-on experience relevant to this role."
    b = item.bullets[0].strip().rstrip(".")
    if _PAST_VERB.match(b):  # "Developed a REST API" -> "I developed a REST API"
        return f"{where}, I {b[0].lower()}{b[1:]}."
    return f"{where}: {b}."


def draft(session: Session, job: Job, item_codes: list[str] | None = None) -> dict:
    p = get_profile(session)
    edu = effective_education(session, p)
    codes = [c.upper() for c in (item_codes if item_codes is not None else suggest_items(session, job))][:2]
    bank = {i.code.upper(): i for i in session.exec(select(ExperienceItem)).all()}
    chosen = [bank[c] for c in codes if c in bank]
    skills = matched_skills(session, job)
    company = job.company or "your company"

    who = "a graduate"
    if edu:
        field = f" in {edu.field}" if edu.field else ""
        who = f"a final-year {edu.level} student{field}" if edu.in_progress else f"a {edu.level} graduate{field}"
    paragraphs = [f"I am writing to apply for the {job.title} position at {company}. As {who}, "
                  f"I am keen to start my career in a role like this one."]
    if skills:
        listed = skills[0] if len(skills) == 1 else ", ".join(skills[:-1]) + f" and {skills[-1]}"
        paragraphs.append(f"The skills I would bring to this role include {listed}.")
    for it in chosen:
        paragraphs.append(item_sentence(it))
    paragraphs.append(f"I would welcome the chance to discuss how I can contribute to {company}. "
                      "Thank you for your time and consideration.")
    return {"greeting": "Dear Hiring Manager,", "paragraphs": paragraphs, "closing": "Sincerely,",
            "used_ids": [it.code for it in chosen], "skills": skills}
