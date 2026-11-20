from collections.abc import Sequence
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.db import get_session
from app.settings_store import get_location_map
from filters.service import apply_to_job, load_rules
from matcher.service import Scorer, rescore_all
from models import Application, Job, MatchResult, Source, StatusHistory
from models._base import require_id
from sources import health, smart_paste
from sources.base import NormalizedJob
from sources.http import PoliteClient, SourceError
from sources.ingest import SUMMARY_ONLY, ingest, is_summary_only, low_confidence
from sources.jobstreet import JobStreetSource, job_id_from_url
from sources.manual import FetchError, fetch_url

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _summary(job: Job, mr: MatchResult | None, app: Application | None) -> dict:
    return {
        **job.model_dump(exclude={"description"}),
        "score": mr.total if mr else None,
        "gate_flags": mr.gate_flags if mr else [],
        "summary_only": is_summary_only(job),
        "low_confidence": low_confidence(mr),
        "application_id": app.id if app else None,
        "application_status": app.status if app else None,
    }


@router.get("")
def list_jobs(session: Session = Depends(get_session)):
    scores = {m.job_id: m for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    apps = {a.job_id: a for a in session.exec(select(Application)).all()}
    jobs = session.exec(select(Job).order_by(col(Job.fetched_at).desc())).all()
    return [_summary(j, scores.get(require_id(j)), apps.get(require_id(j))) for j in jobs]


@router.get("/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    mr = session.exec(select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.method == "quick")).first()
    app = session.exec(select(Application).where(Application.job_id == job_id)).first()
    history: Sequence[StatusHistory] = []
    if app:
        history = session.exec(select(StatusHistory).where(StatusHistory.application_id == app.id)
                               .order_by(col(StatusHistory.changed_at), col(StatusHistory.id))).all()
    return {
        "job": job,
        "summary_only": is_summary_only(job),
        "low_confidence": low_confidence(mr),
        "match": mr,
        "application": app,
        "history": history,
    }


class FullDescription(BaseModel):
    """The full JD pasted for an existing job (usually a "Summary only" one). Other fields only fill blanks."""
    description: str
    location: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    job_type: str = ""
    work_arrangement: str = ""


@router.post("/{job_id}/full-description")
def set_full_description(job_id: int, data: FullDescription, session: Session = Depends(get_session)):
    """Update THIS job from a pasted page (never creates a new job): new description, filters, rescore."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    text = data.description.strip()
    if not text or SUMMARY_ONLY in text:
        raise HTTPException(422, "Paste the full job description first")
    job.description = text
    for f in ("location", "salary_min", "salary_max", "salary_currency", "job_type", "work_arrangement"):
        if not getattr(job, f) and getattr(data, f):
            setattr(job, f, getattr(data, f))
    session.add(job)
    session.flush()
    apply_to_job(job, load_rules(session))
    mr = Scorer(session).score(job)
    session.commit()
    return {"ok": True, "score": mr.total if mr else None, "hidden": job.hidden, "hidden_reason": job.hidden_reason}


class ManualJob(BaseModel):
    title: str
    company: str = ""
    location: str = ""
    description: str
    url: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    job_type: str = ""
    work_arrangement: str = ""
    posted_date: date | None = None
    external_ids: dict[str, str] = {}  # e.g. {"jobstreet": "95667394"} from a JobStreet link


@router.post("/manual")
def import_manual(data: ManualJob, session: Session = Depends(get_session)):
    if not data.title.strip() or not data.description.strip():
        raise HTTPException(422, "Title and JD text are required")
    fields = data.model_dump(exclude={"external_ids"})
    nj = NormalizedJob(**fields, source="jobstreet" if data.external_ids.get("jobstreet") else "manual",
                       extra={"external_ids": data.external_ids})
    job, dup = ingest(session, [nj])[0]
    return {"id": job.id, "duplicate": dup, "hidden": job.hidden, "hidden_reason": job.hidden_reason}


class UrlRequest(BaseModel):
    url: str


@router.post("/fetch-url")
def fetch_job_url(req: UrlRequest, session: Session = Depends(get_session)):
    """Best effort. Returns a draft for the import form; nothing is saved.

    JobStreet links go through the JobStreet module by job ID (same safety rules and pause as fetching);
    other links get one plain page fetch.
    """
    js = job_id_from_url(req.url.strip())
    if js:
        return _jobstreet_draft(session, *js)
    try:
        nj = fetch_url(req.url)
    except FetchError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "draft": {
        "title": nj.title, "company": nj.company, "location": nj.location, "description": nj.description,
        "url": nj.url or req.url, "salary_min": nj.salary_min, "salary_max": nj.salary_max,
        "salary_currency": nj.salary_currency, "job_type": nj.job_type,
    }}


def _jobstreet_draft(session: Session, country: str, job_id: str) -> dict:
    src = session.get(Source, "jobstreet")
    existing = next((j for j in session.exec(select(Job)).all() if j.external_ids.get("jobstreet") == job_id), None)
    if existing:  # never re-fetch a job that is already stored
        return {"ok": False, "existing_id": existing.id,
                "error": f"This JobStreet job is already saved: “{existing.title}”."}
    if src is not None:
        health.refresh(src)
        if not src.enabled:
            return {"ok": False, "error": "JobStreet is switched off in Settings → Job sources. Paste the page text instead."}
        if src.status == "paused":
            return {"ok": False, "error": f"JobStreet is paused ({src.last_error}). Paste the page text instead."}
    client = PoliteClient()
    try:
        full = JobStreetSource(client, country=country).detail(job_id)
    except SourceError as e:
        if src is not None:
            health.record_failure(session, src, e)
            session.commit()
        return {"ok": False, "error": f"JobStreet: {e}. Paste the page text instead."}
    finally:
        client.close()
    nj = JobStreetSource(client, country=country).to_normalized(
        {"id": job_id, "title": full["title"], "teaser": "", "bullets": []}, full)
    if src is not None:
        health.record_success(src, f"URL import of job {job_id}")
        session.commit()
    return {"ok": True, "draft": {
        "title": nj.title, "company": nj.company, "location": nj.location, "description": nj.description,
        "url": nj.url, "salary_min": nj.salary_min, "salary_max": nj.salary_max, "salary_currency": nj.salary_currency,
        "job_type": nj.job_type, "work_arrangement": nj.work_arrangement, "external_ids": {"jobstreet": job_id},
    }}


class PasteRequest(BaseModel):
    text: str


@router.post("/parse-paste")
def parse_paste(req: PasteRequest, session: Session = Depends(get_session)):
    """Whole copied job page -> editable draft (title/company/location/salary + cleaned JD). Nothing is saved."""
    if not req.text.strip():
        raise HTTPException(422, "Paste the job page text first")
    d = smart_paste.extract(req.text, get_location_map(session))
    return {**d.__dict__, "url": ""}


class JobPatch(BaseModel):
    hidden: bool | None = None
    hidden_reason: str | None = None  # with hidden=true, e.g. "Not interested" from Today
    # Undo of a Hide: back to how it was before, so filter rules decide again (a plain unhide is final).
    restore: bool = False


@router.patch("/{job_id}")
def patch_job(job_id: int, data: JobPatch, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if data.restore:
        job.hidden, job.hidden_by, job.hidden_reason = False, "", ""
        apply_to_job(job, load_rules(session))  # the rules decide again, as before the Hide
    elif data.hidden is not None:
        # A manual choice (hide or unhide) is final: filter rules no longer touch this job.
        job.hidden = data.hidden
        job.hidden_by = "manual"
        reason = (data.hidden_reason or "").strip()
        job.hidden_reason = (reason or "Hidden manually") if data.hidden else ""
    session.add(job)
    session.commit()
    return {"ok": True}


@router.delete("/{job_id}")
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    session.delete(job)
    session.commit()
    return {"ok": True}


@router.post("/rescore")
def rescore(session: Session = Depends(get_session)):
    return {"rescored": rescore_all(session)}
