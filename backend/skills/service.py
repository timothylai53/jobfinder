"""Skill dictionary persistence: seeding and building a matcher from the DB."""
import json
from pathlib import Path

from sqlmodel import Session, select

from models import AppSetting, Skill
from skills.matcher import SkillDef, SkillMatcher

SEED_FILE = Path(__file__).with_name("seed_skills.json")


def _seed_rows() -> list[dict]:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def load_seed() -> list[SkillDef]:
    return [SkillDef(name=r["name"], aliases=r.get("aliases", []), category=r.get("category", "other")) for r in _seed_rows()]


SEED_VERSION_KEY = "skills_seed_version"


def _set_seed_version(session: Session, v: int) -> None:
    row = session.get(AppSetting, SEED_VERSION_KEY)
    if row:
        row.value = v
    else:
        session.add(AppSetting(key=SEED_VERSION_KEY, value=v))


def seed_if_empty(session: Session) -> int:
    """First run: the whole dictionary. Later runs: only entries added to the seed since last time
    (tagged "since": N), so skills I deleted are never re-added."""
    rows = _seed_rows()
    latest = max(r.get("since", 1) for r in rows)
    if session.exec(select(Skill.id).limit(1)).first() is None:
        for r in rows:
            session.add(Skill(name=r["name"], category=r.get("category", "other"), aliases=r.get("aliases", [])))
        _set_seed_version(session, latest)
        session.commit()
        return len(rows)
    row = session.get(AppSetting, SEED_VERSION_KEY)
    current = int(row.value) if row and row.value is not None else 1
    if current >= latest:
        return 0
    have = {n.lower() for n in session.exec(select(Skill.name)).all()}
    added = 0
    for r in rows:
        if r.get("since", 1) > current and r["name"].lower() not in have:
            session.add(Skill(name=r["name"], category=r.get("category", "other"), aliases=r.get("aliases", [])))
            added += 1
    _set_seed_version(session, latest)
    session.commit()
    return added


# Aliases removed from the seed after release: dropped from existing dictionaries once (idempotent).
# "Version control" matched drawings' "version control" in a Draughtman ad (13 Nov).
REMOVED_ALIASES = {"Git": ["Version control"]}


def remove_retired_aliases(session: Session) -> int:
    removed = 0
    for name, gone in REMOVED_ALIASES.items():
        skill = session.exec(select(Skill).where(Skill.name == name)).first()
        if skill is None:
            continue
        keep = [a for a in skill.aliases if a.lower() not in {g.lower() for g in gone}]
        if len(keep) != len(skill.aliases):
            removed += len(skill.aliases) - len(keep)
            skill.aliases = keep
    session.commit()
    return removed


def build_matcher(session: Session) -> SkillMatcher:
    rows = session.exec(select(Skill).order_by(Skill.id)).all()
    return SkillMatcher([SkillDef(name=r.name, aliases=list(r.aliases), category=r.category) for r in rows])
