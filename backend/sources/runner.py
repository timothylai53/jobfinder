"""Fetch jobs from every enabled source for every enabled search profile.

Per source: safety check (enabled / not paused / daily runs left) -> fetch, one profile after another ->
classify failures (429/403 -> 24 h pause + notification; 3 errors in a row -> pause) -> the SAME ingest
pipeline as manual import (dedupe -> filters -> JD snapshot -> quick score). One failing source never
stops the others, and jobs fetched before a failure are still saved.
"""
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, col, select

from models import Job, SearchProfile, Source
from models._base import require_id, utcnow
from sources import health
from sources.base import NormalizedJob
from sources.http import PoliteClient, RateLimited, SourceError
from sources.ingest import ingest
from sources.jobspy_source import JOBSPY_SITES, JobSpySource
from sources.jobstreet import JobStreetSource

SOURCE_ORDER = ["jobstreet", "linkedin", "indeed", "glassdoor"]

# Sources with a fetch in progress (this process): a second Fetch for the same source is refused.
_running: set[str] = set()
_running_lock = threading.Lock()


def running_sources() -> set[str]:
    with _running_lock:
        return set(_running)


def _claim(key: str) -> bool:
    with _running_lock:
        if key in _running:
            return False
        _running.add(key)
        return True


def _release(key: str) -> None:
    with _running_lock:
        _running.discard(key)


@dataclass
class SourceResult:
    key: str
    status: str = "ok"  # ok / skipped / error / paused
    message: str = ""
    fetched: int = 0
    new: int = 0
    merged: int = 0
    hidden: int = 0
    requests: int = 0
    cap: int | None = None  # the per-run limit actually used
    profiles: list[str] = field(default_factory=list)  # search profile names actually used
    new_job_ids: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # warnings worth reading (JobSpy, blocked pages, coverage)
    error: str = ""  # why the source stopped, if it did

    def label(self) -> str:
        """"indeed (limit 5, profile Smoke test)": what this run really used, for the run log."""
        if self.cap is None:
            return self.key
        names = ", ".join(self.profiles) or "none"
        return f"{self.key} (limit {self.cap}, profile{'s' if len(self.profiles) > 1 else ''} {names})"


def _known(session: Session, key: str) -> set[str]:
    known: set[str] = set()
    for job in session.exec(select(Job)).all():
        if job.external_ids.get(key):
            known.add(job.external_ids[key])
        if key != "jobstreet":
            known.update(u for u in job.urls if key in u)
    return known


def build_source(key: str, session: Session, cap: int, sleep: Callable[[float], None] | None = None,
                 now: datetime | None = None):
    if key == "jobstreet":
        client = PoliteClient(sleep=sleep) if sleep else PoliteClient()
        return JobStreetSource(client, max_results=cap, known_ids=_known(session, key), now=now)
    if key in JOBSPY_SITES:
        if sleep:
            return JobSpySource(key, max_results=cap, known=_known(session, key), sleep=sleep)
        return JobSpySource(key, max_results=cap, known=_known(session, key))
    raise ValueError(f"unknown source {key}")


def run_fetch(session: Session, source_keys: list[str] | None = None, profile_ids: list[int] | None = None,
              results_cap: int | None = None, now: datetime | None = None,
              sleep: Callable[[float], None] | None = None) -> list[SourceResult]:
    now = now or utcnow()
    profiles = [p for p in session.exec(select(SearchProfile).order_by(col(SearchProfile.id))).all()
                if p.enabled and (profile_ids is None or p.id in profile_ids)]
    results: list[SourceResult] = []
    for key in SOURCE_ORDER:
        if source_keys is not None and key not in source_keys:
            continue
        src = session.get(Source, key)
        res = SourceResult(key)
        results.append(res)
        if src is None:
            res.status, res.message = "skipped", "unknown source"
            continue
        ok, why = health.can_run(src, now)
        mine = [p for p in profiles if not p.sources or key in p.sources]
        if not ok or not mine:
            res.status, res.message = "skipped", why or "no enabled search profile uses this source"
            session.commit()
            continue
        if not _claim(key):
            res.status, res.message = "skipped", "a fetch for this source is already running"
            continue
        try:
            _fetch_one(session, src, res, mine, results_cap, now, sleep)
        finally:
            _release(key)
    return results


def _fetch_one(session: Session, src: Source, res: SourceResult, mine: list[SearchProfile], results_cap: int | None,
               now: datetime, sleep: Callable[[float], None] | None) -> None:
    key = src.key
    health.clamp_limits(src)
    cap = min(src.max_results, results_cap) if results_cap else src.max_results
    res.cap, res.profiles = cap, [p.name for p in mine]
    health.record_run(src, now)
    session.commit()

    impl = build_source(key, session, cap, sleep, now)
    jobs: list[NormalizedJob] = []
    error: SourceError | None = None
    try:
        for p in mine:
            remaining = cap - len(jobs)
            if remaining <= 0:
                break
            impl.max_results = remaining
            jobs += impl.fetch(p)
    except (SourceError, Exception) as e:  # noqa: BLE001 - one source must never break the others
        error = e if isinstance(e, SourceError) else SourceError(f"{e.__class__.__name__}: {e}")
        jobs += [j for j in getattr(impl, "collected", []) if j not in jobs]
    finally:
        client = getattr(impl, "client", None)
        # JobSpy calls (each = 1+ search pages) + our own paced requests (JobStreet, LinkedIn job pages)
        res.requests = getattr(impl, "calls", 0) + (getattr(client, "requests_made", 0) if client else 0)
        if client is not None:
            client.close()

    res.fetched = len(jobs)
    try:
        for job, dup in ingest(session, jobs) if jobs else []:
            if dup:
                res.merged += 1
            else:
                res.new += 1
                res.new_job_ids.append(require_id(job))
                res.hidden += job.hidden
    except Exception as e:  # noqa: BLE001 - e.g. a locked database: record it on the source, never crash the run
        session.rollback()
        res.new = res.merged = res.hidden = 0
        res.new_job_ids = []
        error = error or SourceError(f"saving the fetched jobs failed ({e.__class__.__name__}: {e})")
    res.notes = list(getattr(impl, "notes", []))
    notes = "; ".join(res.notes)
    summary = f"{res.fetched} fetched, {res.new} new, {res.merged} merged, {res.hidden} hidden by filters"
    if error is None:
        health.record_success(src, summary + (f". {notes}" if notes else ""))
        res.message = src.last_result
    else:
        health.record_failure(session, src, error, now)
        res.error = str(error)
        res.status = "paused" if src.status == "paused" else "error"
        tail = f". Saved before stopping: {summary}" + (f". {notes}" if notes else "")
        res.message = f"{src.last_error}{tail}"
        src.last_result = res.message
        if isinstance(error, RateLimited):
            res.message = f"Stopped on {error}: paused for 24 h{tail}"
    session.commit()
