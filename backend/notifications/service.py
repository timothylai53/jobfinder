"""In-app notifications (the bell). Desktop notifications are optional and not implemented (off by default)."""
from sqlmodel import Session, select

from models import Notification


def notify(session: Session, type_: str, message: str, link: str = "") -> Notification:
    n = Notification(type=type_, message=message, link=link)
    session.add(n)
    return n


def unread_count(session: Session) -> int:
    return len(session.exec(select(Notification.id).where(Notification.read == False)).all())  # noqa: E712
