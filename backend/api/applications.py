from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.db import get_session
from app.settings_store import get_general
from models import Application, Document, Job, MatchResult, StatusHistory
from models._base import utcnow
from tracker import service

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("")
def list_applications(session: Session = Depends(get_session)):
    jobs = {j.id: j for j in session.exec(select(Job)).all()}
    scores = {m.job_id: m.total for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    out = []
    for a in session.exec(select(Application).order_by(col(Application.updated_at).desc())).all():
        j = jobs.get(a.job_id)
        out.append({**a.model_dump(), "job_title": j.title if j else "", "company": j.company if j else "",
                    "location": j.location if j else "", "score": scores.get(a.job_id)})
    return out


class CreateApp(BaseModel):
    job_id: int
    status: str = "Saved"


@router.post("")
def create_application(req: CreateApp, session: Session = Depends(get_session)):
    if not session.get(Job, req.job_id):
        raise HTTPException(404, "Job not found")
    existing = session.exec(select(Application).where(Application.job_id == req.job_id)).first()
    if existing:
        return {"id": existing.id, "existing": True}
    try:
        app = service.create(session, req.job_id, req.status, get_general(session).follow_up_days)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    session.commit()
    return {"id": app.id, "existing": False}


class PatchApp(BaseModel):
    status: str | None = None
    notes: str | None = None
    applied_at: date | None = None
    follow_up_at: date | None = None
    resume_version_id: int | None = None  # the Document versions I actually sent (null clears)
    cover_letter_version_id: int | None = None


@router.patch("/{app_id}")
def patch_application(app_id: int, req: PatchApp, session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    upd = req.model_dump(exclude_unset=True)
    for k in ("notes", "applied_at", "follow_up_at"):
        if k in upd:
            setattr(app, k, upd[k])
    for k, type_ in (("resume_version_id", "resume"), ("cover_letter_version_id", "cover_letter")):
        if k in upd:
            doc = session.get(Document, upd[k]) if upd[k] is not None else None
            if upd[k] is not None and (doc is None or doc.type != type_ or doc.job_id != app.job_id):
                raise HTTPException(422, f"{k}: not a {type_.replace('_', ' ')} version of this job")
            setattr(app, k, upd[k])
    if "applied_at" in upd and "follow_up_at" not in upd and upd["applied_at"] and app.follow_up_at is None:
        app.follow_up_at = upd["applied_at"] + timedelta(days=get_general(session).follow_up_days)
    if upd.get("status"):
        try:
            service.change_status(session, app, upd["status"], get_general(session).follow_up_days)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
    app.updated_at = utcnow()
    session.add(app)
    session.commit()
    session.refresh(app)
    return app


@router.get("/{app_id}/history", response_model=list[StatusHistory])
def history(app_id: int, session: Session = Depends(get_session)):
    return session.exec(select(StatusHistory).where(StatusHistory.application_id == app_id)
                        .order_by(col(StatusHistory.changed_at), col(StatusHistory.id))).all()


@router.delete("/{app_id}")
def delete_application(app_id: int, session: Session = Depends(get_session)):
    app = session.get(Application, app_id)
    if not app:
        raise HTTPException(404, "Application not found")
    session.delete(app)
    session.commit()
    return {"ok": True}
