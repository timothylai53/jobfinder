"""Sources (health + limits), search profiles, and "Fetch now"."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.db import engine, get_session
from models import SearchProfile, SearchProfileBase, Source
from scheduler.automations import run_in_background
from sources import health
from sources.http import fake_mode
from sources.runner import SOURCE_ORDER, running_sources

router = APIRouter(prefix="/api", tags=["sources"])


def _source_out(src: Source) -> dict:
    health.refresh(src)
    label, _e, _r, _m, hard_results, hard_runs = health.SOURCE_DEFAULTS[src.key]
    return {**src.model_dump(), "label": label, "hard_max_results": hard_results, "hard_max_runs_per_day": hard_runs,
            "can_run": health.can_run(src)[0], "running": src.key in running_sources(), "fake_mode": fake_mode()}


@router.get("/sources")
def list_sources(session: Session = Depends(get_session)):
    rows = {s.key: s for s in session.exec(select(Source)).all()}
    out = [_source_out(rows[k]) for k in SOURCE_ORDER if k in rows]
    session.commit()  # refresh() may have lifted an expired pause or rolled the daily counter
    return out


class SourceUpdate(BaseModel):
    enabled: bool
    max_results: int = Field(ge=1)
    max_runs_per_day: int = Field(ge=1)


@router.put("/sources/{key}")
def update_source(key: str, data: SourceUpdate, session: Session = Depends(get_session)):
    src = session.get(Source, key)
    if not src:
        raise HTTPException(404, "Unknown source")
    src.enabled, src.max_results, src.max_runs_per_day = data.enabled, data.max_results, data.max_runs_per_day
    health.clamp_limits(src)  # safe maximums always win
    session.commit()
    return _source_out(src)


@router.post("/sources/{key}/resume")
def resume_source(key: str, session: Session = Depends(get_session)):
    src = session.get(Source, key)
    if not src:
        raise HTTPException(404, "Unknown source")
    health.resume(src)
    session.commit()
    return _source_out(src)


# ---------- search profiles ----------

def _clean_profile(data: SearchProfileBase) -> SearchProfileBase:
    data.name = data.name.strip()
    data.keywords = list(dict.fromkeys(k.strip() for k in data.keywords if k.strip()))
    data.locations = list(dict.fromkeys(k.strip() for k in data.locations if k.strip()))
    data.sources = [s for s in data.sources if s in SOURCE_ORDER]
    if not data.name or not data.keywords:
        raise HTTPException(422, "A search profile needs a name and at least one keyword")
    data.days = max(1, min(data.days, 31))
    data.max_results = max(0, data.max_results)
    return data


@router.get("/search-profiles", response_model=list[SearchProfile])
def list_profiles(session: Session = Depends(get_session)):
    return session.exec(select(SearchProfile).order_by(col(SearchProfile.id))).all()


@router.post("/search-profiles", response_model=SearchProfile)
def create_profile(data: SearchProfileBase, session: Session = Depends(get_session)):
    p = SearchProfile(**_clean_profile(data).model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@router.put("/search-profiles/{pid}", response_model=SearchProfile)
def update_profile(pid: int, data: SearchProfileBase, session: Session = Depends(get_session)):
    p = session.get(SearchProfile, pid)
    if not p:
        raise HTTPException(404, "Search profile not found")
    for k, v in _clean_profile(data).model_dump().items():
        setattr(p, k, v)
    session.commit()
    session.refresh(p)
    return p


@router.delete("/search-profiles/{pid}")
def delete_profile(pid: int, session: Session = Depends(get_session)):
    p = session.get(SearchProfile, pid)
    if not p:
        raise HTTPException(404, "Search profile not found")
    session.delete(p)
    session.commit()
    return {"ok": True}


# ---------- Fetch now ----------

class FetchRequest(BaseModel):
    source_keys: list[str] | None = None  # None = every enabled source
    profile_ids: list[int] | None = None
    results_cap: int | None = Field(None, ge=1, le=100)  # e.g. 5 for the supervised smoke test


@router.post("/fetch")
def fetch_now(req: FetchRequest):
    """Runs fetch_jobs once in the background (works even while its schedule is off). Returns the run id."""
    run_id = run_in_background(engine, "fetch_jobs", "manual", source_keys=req.source_keys,
                               profile_ids=req.profile_ids, results_cap=req.results_cap)
    return {"run_id": run_id}
