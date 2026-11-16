from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app import config
from app.db import get_session
from app.settings_store import next_item_code
from export.backup import backup_db
from matcher.service import rescore_all
from models import BaseResume, ExperienceItem, ExperienceItemBase

router = APIRouter(prefix="/api/experience", tags=["experience"])


@router.get("", response_model=list[ExperienceItem])
def list_items(session: Session = Depends(get_session)):
    return session.exec(select(ExperienceItem).order_by(ExperienceItem.id)).all()


@router.post("", response_model=ExperienceItem)
def create_item(data: ExperienceItemBase, session: Session = Depends(get_session)):
    item = ExperienceItem(**data.model_dump(), code=next_item_code(session))
    session.add(item)
    session.commit()
    rescore_all(session)
    session.refresh(item)
    return item


@router.put("/{item_id}", response_model=ExperienceItem)
def update_item(item_id: int, data: ExperienceItemBase, session: Session = Depends(get_session)):
    item = session.get(ExperienceItem, item_id)
    if not item:
        raise HTTPException(404, "Experience item not found")
    for k, v in data.model_dump().items():
        setattr(item, k, v)
    session.add(item)
    session.commit()
    rescore_all(session)
    session.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(ExperienceItem, item_id)
    if not item:
        raise HTTPException(404, "Experience item not found")
    session.delete(item)
    session.commit()
    rescore_all(session)
    return {"ok": True}


@router.post("/clear")
def clear_bank(session: Session = Depends(get_session)):
    """Delete every Experience Bank item and BaseResume. A database backup is made first.
    Profile fields and the skill dictionary are kept; item IDs are never reused (B-numbers continue)."""
    backup = backup_db(config.DB_PATH, config.BACKUPS_DIR)
    items = session.exec(select(ExperienceItem)).all()
    resumes = session.exec(select(BaseResume)).all()
    for row in [*items, *resumes]:
        session.delete(row)
    session.commit()
    rescore_all(session)
    return {"backup": backup.name, "deleted_items": len(items), "deleted_resumes": len(resumes)}
