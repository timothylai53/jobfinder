from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.db import get_session
from models import Notification
from notifications.service import unread_count

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(limit: int = 30, session: Session = Depends(get_session)):
    rows = session.exec(select(Notification).order_by(col(Notification.id).desc()).limit(min(limit, 200))).all()
    return {"unread": unread_count(session), "items": rows}


@router.post("/{nid}/read")
def mark_read(nid: int, session: Session = Depends(get_session)):
    n = session.get(Notification, nid)
    if not n:
        raise HTTPException(404, "Notification not found")
    n.read = True
    session.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(session: Session = Depends(get_session)):
    for n in session.exec(select(Notification).where(Notification.read == False)).all():  # noqa: E712
        n.read = True
    session.commit()
    return {"ok": True}
