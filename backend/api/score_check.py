"""Score check: I rate a job's score (too high / about right / too low); the report says how often the score agrees
with me, by score band, and which jobs it got wrong."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.db import get_session
from export.excel_csv import _text
from models import Job, MatchResult
from models._base import utcnow
from models.rating import RATINGS, ScoreRating

router = APIRouter(prefix="/api", tags=["score-check"])

BANDS = (("0-49", 0, 49), ("50-69", 50, 69), ("70+", 70, 100))


class RatingIn(BaseModel):
    rating: str
    note: str = Field(default="", max_length=300)


def _out(r: ScoreRating) -> dict:
    return {"job_id": r.job_id, "rating": r.rating, "note": r.note, "score_at": r.score_at,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat()}


def _current_score(session: Session, job_id: int) -> int | None:
    m = session.exec(select(MatchResult).where(MatchResult.job_id == job_id, MatchResult.method == "quick")).first()
    return m.total if m else None


@router.get("/jobs/{job_id}/rating")
def get_rating(job_id: int, session: Session = Depends(get_session)):
    r = session.exec(select(ScoreRating).where(ScoreRating.job_id == job_id)).first()
    return _out(r) if r else None


@router.put("/jobs/{job_id}/rating")
def set_rating(job_id: int, data: RatingIn, session: Session = Depends(get_session)):
    if data.rating not in RATINGS:
        raise HTTPException(422, f"rating must be one of {', '.join(RATINGS)}")
    if session.get(Job, job_id) is None:
        raise HTTPException(404, "Job not found")
    r = session.exec(select(ScoreRating).where(ScoreRating.job_id == job_id)).first()
    score = _current_score(session, job_id)
    if r is None:
        r = ScoreRating(job_id=job_id, rating=data.rating, note=data.note.strip(), score_at=score)
    else:
        if r.rating != data.rating:  # a new verdict is about the score as it is now
            r.score_at = score
        r.rating, r.note, r.updated_at = data.rating, data.note.strip(), utcnow()
    session.add(r)
    session.commit()
    session.refresh(r)
    return _out(r)


@router.delete("/jobs/{job_id}/rating")
def clear_rating(job_id: int, session: Session = Depends(get_session)):
    r = session.exec(select(ScoreRating).where(ScoreRating.job_id == job_id)).first()
    if r:
        session.delete(r)
        session.commit()
    return {"ok": True}


def _rows(session: Session) -> list[dict]:
    jobs = {j.id: j for j in session.exec(select(Job)).all()}
    scores = {m.job_id: m.total for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    out = []
    for r in session.exec(select(ScoreRating).order_by(col(ScoreRating.updated_at).desc())).all():
        j = jobs.get(r.job_id)
        if j is None:
            continue
        out.append({**_out(r), "title": j.title, "company": j.company, "score_now": scores.get(r.job_id)})
    return out


def report(session: Session) -> dict:
    rows = _rows(session)

    def summary(items: list[dict]) -> dict:
        n = len(items)
        count = {k: sum(1 for x in items if x["rating"] == k) for k in RATINGS}
        return {"rated": n, **count, "agree_pct": round(100 * count["about_right"] / n) if n else None}

    bands = []
    for label, lo, hi in BANDS:
        in_band = [x for x in rows if x["score_at"] is not None and lo <= x["score_at"] <= hi]
        bands.append({"band": label, **summary(in_band)})
    return {**summary(rows), "bands": bands, "misses": [x for x in rows if x["rating"] != "about_right"]}


@router.get("/score-check")
def score_check(session: Session = Depends(get_session)):
    return report(session)


@router.get("/score-check.csv")
def score_check_csv(session: Session = Depends(get_session)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["job_id", "title", "company", "score_at_rating", "score_now", "rating", "note", "rated_at"])
    for x in _rows(session):
        # Titles and notes can start with "=" etc.: kept as text so a spreadsheet never runs them (same guard as the exports).
        w.writerow([x["job_id"], _text(x["title"]), _text(x["company"]), x["score_at"], x["score_now"], x["rating"],
                    _text(x["note"]), x["updated_at"]])
    return Response(("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="score-check.csv"'})
