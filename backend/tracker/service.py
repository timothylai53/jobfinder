"""Application status changes (always recorded in StatusHistory) and follow-up dates."""
from datetime import date, timedelta

from sqlmodel import Session

from models import STATUSES, Application, StatusHistory
from models._base import require_id, utcnow


def create(session: Session, job_id: int, status: str = "Saved", follow_up_days: int = 7) -> Application:
    app = Application(job_id=job_id, status="Saved")
    session.add(app)
    session.flush()
    session.add(StatusHistory(application_id=require_id(app), from_status=None, to_status="Saved"))
    if status != "Saved":
        change_status(session, app, status, follow_up_days)
    return app


def change_status(session: Session, app: Application, new: str, follow_up_days: int = 7,
                  today: date | None = None) -> bool:
    if new not in STATUSES:
        raise ValueError(f"Unknown status {new!r}; expected one of {', '.join(STATUSES)}")
    if new == app.status:
        return False
    session.add(StatusHistory(application_id=require_id(app), from_status=app.status, to_status=new))
    app.status = new
    if new == "Applied" and app.applied_at is None:
        app.applied_at = today or date.today()
    if new == "Applied" and app.follow_up_at is None and app.applied_at:
        app.follow_up_at = app.applied_at + timedelta(days=follow_up_days)
    app.updated_at = utcnow()
    return True
