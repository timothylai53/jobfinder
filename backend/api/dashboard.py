from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.settings_store import get_general
from models import STATUSES, Application, Job, MatchResult, Notification, Source, StatusHistory
from models._base import utcnow

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
RESPONSE_STATUSES = {"Interview", "Offer", "Rejected"}


def weekly_counts(applied: list[date], today: date, weeks: int = 8) -> list[dict]:
    """Applications per ISO week (Monday start), oldest first."""
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=i)
        end = start + timedelta(days=7)
        out.append({"week_start": start.isoformat(), "count": sum(start <= d < end for d in applied)})
    return out


def response_rate(apps: list[Application], history: list[StatusHistory]) -> float | None:
    """Share of applied applications that reached Interview / Offer / Rejected."""
    applied_ids = {a.id for a in apps if a.applied_at or a.status in RESPONSE_STATUSES | {"Applied"}}
    applied_ids |= {h.application_id for h in history if h.to_status == "Applied"}
    if not applied_ids:
        return None
    responded = {h.application_id for h in history if h.to_status in RESPONSE_STATUSES} & applied_ids
    return round(100 * len(responded) / len(applied_ids), 1)


def _source_health(session: Session) -> list[dict]:
    from sources import health
    from sources.runner import SOURCE_ORDER

    out = []
    for key in SOURCE_ORDER:
        src = session.get(Source, key)
        if src is None:
            continue
        health.refresh(src)
        status = "disabled" if not src.enabled else src.status
        note = src.last_error if status in ("error", "paused") else (src.last_result or "not run yet")
        out.append({"key": key, "label": health.SOURCE_DEFAULTS[key][0], "status": status, "note": note,
                    "paused_until": src.paused_until.isoformat() if src.paused_until else None,
                    "last_run_at": src.last_run_at.isoformat() if src.last_run_at else None})
    return out


@router.get("")
def dashboard(session: Session = Depends(get_session)):
    apps = session.exec(select(Application)).all()
    history = session.exec(select(StatusHistory)).all()
    threshold = get_general(session).high_match_threshold
    tracked = {a.job_id for a in apps}
    since = utcnow() - timedelta(days=7)
    jobs = {j.id: j for j in session.exec(select(Job).where(Job.hidden == False)).all()}  # noqa: E712
    high = []
    for m in session.exec(select(MatchResult).where(MatchResult.method == "quick", MatchResult.total >= threshold)).all():
        j = jobs.get(m.job_id)
        if j and j.id not in tracked and j.fetched_at >= since:
            high.append({"id": j.id, "title": j.title, "company": j.company, "score": m.total})
    high.sort(key=lambda x: -x["score"])
    today = date.today()
    return {
        "status_counts": {s: sum(a.status == s for a in apps) for s in STATUSES},
        "applications_per_week": weekly_counts([a.applied_at for a in apps if a.applied_at], today),
        "response_rate": response_rate(apps, history),
        "high_match_jobs": high[:10],
        "high_match_threshold": threshold,
        "unread_notifications": len(session.exec(select(Notification.id).where(Notification.read == False)).all()),  # noqa: E712
        "follow_ups_due": sum(1 for a in apps if a.status == "Applied" and a.follow_up_at and a.follow_up_at <= today),
        "total_jobs": len(jobs),
        "sources": _source_health(session),
    }
