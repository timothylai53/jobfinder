from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from matcher.service import rescore_all
from models import Skill, SkillBase

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _clean(data: SkillBase) -> SkillBase:
    data.name = data.name.strip()
    data.aliases = list(dict.fromkeys(a.strip() for a in data.aliases if a.strip() and a.strip() != data.name))
    if not data.name:
        raise HTTPException(422, "Skill name is required")
    return data


def _check_unique(session: Session, name: str, exclude_id: int | None = None):
    for s in session.exec(select(Skill)).all():
        if s.id != exclude_id and s.name.lower() == name.lower():
            raise HTTPException(409, f"Skill {name!r} already exists")


@router.get("", response_model=list[Skill])
def list_skills(session: Session = Depends(get_session)):
    return session.exec(select(Skill).order_by(Skill.category, Skill.name)).all()


@router.post("", response_model=Skill)
def create_skill(data: SkillBase, session: Session = Depends(get_session)):
    data = _clean(data)
    _check_unique(session, data.name)
    s = Skill(**data.model_dump())
    session.add(s)
    session.commit()
    rescore_all(session)
    session.refresh(s)
    return s


@router.put("/{skill_id}", response_model=Skill)
def update_skill(skill_id: int, data: SkillBase, session: Session = Depends(get_session)):
    s = session.get(Skill, skill_id)
    if not s:
        raise HTTPException(404, "Skill not found")
    data = _clean(data)
    _check_unique(session, data.name, skill_id)
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    session.add(s)
    session.commit()
    rescore_all(session)
    session.refresh(s)
    return s


@router.delete("/{skill_id}")
def delete_skill(skill_id: int, session: Session = Depends(get_session)):
    s = session.get(Skill, skill_id)
    if not s:
        raise HTTPException(404, "Skill not found")
    session.delete(s)
    session.commit()
    rescore_all(session)
    return {"ok": True}
