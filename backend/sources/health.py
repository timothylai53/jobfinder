"""Source health and the scraping-safety rules (brief §6.3).

- at most `max_runs_per_day` runs per source per day; results capped per run (with hard maxima);
- HTTP 429/403, or 3 consecutive errors -> pause that source for 24 h, record why, notify;
- a paused source is skipped until `paused_until` passes (or I resume it by hand).
"""
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from models import SearchProfile, Source
from models._base import utcnow
from notifications.service import notify
from sources.http import RateLimited

PAUSE = timedelta(hours=24)
ERRORS_BEFORE_PAUSE = 3

# key: (label, enabled by default, results per run, runs per day, hard max results, hard max runs/day)
SOURCE_DEFAULTS = {
    "jobstreet": ("JobStreet", True, 50, 2, 100, 2),
    "linkedin": ("LinkedIn", True, 15, 1, 30, 2),
    "indeed": ("Indeed", True, 50, 2, 100, 2),
    "glassdoor": ("Glassdoor", False, 50, 2, 100, 2),
}

DEFAULT_PROFILES = [
    {"name": "KL/Selangor", "locations": ["Kuala Lumpur", "Selangor", "Remote"]},
    {"name": "Sabah", "locations": ["Sabah"]},
]
# Entry-level terms (after the 13 Nov LinkedIn smoke test returned mostly Senior roles for "software engineer").
DEFAULT_KEYWORDS = ["junior software engineer", "graduate software engineer", "software developer", "fresh graduate IT"]
# Earlier defaults: a default profile still using one of these exactly is moved to DEFAULT_KEYWORDS once.
OLD_DEFAULT_KEYWORDS = [
    ["software engineer", "software developer", "full stack developer"],
    ["software engineer", "junior software engineer", "graduate software engineer", "full stack developer"],
]


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def seed(session: Session) -> None:
    for key, (_label, enabled, results, runs, _hr, _hm) in SOURCE_DEFAULTS.items():
        if session.get(Source, key) is None:
            session.add(Source(key=key, enabled=enabled, max_results=results, max_runs_per_day=runs))
    if session.exec(select(SearchProfile.id).limit(1)).first() is None:
        for p in DEFAULT_PROFILES:
            session.add(SearchProfile(name=str(p["name"]), keywords=list(DEFAULT_KEYWORDS), locations=list(p["locations"]),
                                      job_type="fulltime", days=7))
    else:
        update_default_keywords(session)
    session.commit()


def update_default_keywords(session: Session) -> int:
    """The default profiles (by name) still on an old default keyword list get the new one. Profiles I edited
    myself, and any other profile (e.g. "Smoke test"), are left alone."""
    names = {p["name"] for p in DEFAULT_PROFILES}
    changed = 0
    for p in session.exec(select(SearchProfile)).all():
        if p.name in names and list(p.keywords) in OLD_DEFAULT_KEYWORDS:
            p.keywords = list(DEFAULT_KEYWORDS)
            changed += 1
    return changed


def clamp_limits(src: Source) -> None:
    _l, _e, _r, _m, hard_results, hard_runs = SOURCE_DEFAULTS.get(src.key, ("", True, 50, 2, 100, 2))
    src.max_results = max(1, min(src.max_results, hard_results))
    src.max_runs_per_day = max(1, min(src.max_runs_per_day, hard_runs))


def refresh(src: Source, now: datetime | None = None) -> None:
    """Roll the daily counter over and lift an expired pause."""
    now = now or utcnow()
    today = now.astimezone().date()  # the local calendar day (Malaysia is UTC+8)
    if src.runs_date != today:
        src.runs_date, src.runs_today = today, 0
    if src.status == "paused" and src.paused_until and _aware(src.paused_until) <= now:
        src.status, src.paused_until, src.consecutive_errors = "ok", None, 0


def can_run(src: Source, now: datetime | None = None) -> tuple[bool, str]:
    refresh(src, now)
    if not src.enabled:
        return False, "disabled"
    if src.status == "paused":
        # A pause always has an end time; if one ever doesn't, say so instead of crashing on None.
        until = f"until {_aware(src.paused_until):%Y-%m-%d %H:%M} UTC" if src.paused_until else "(no end time set)"
        return False, f"paused {until}"
    if src.runs_today >= src.max_runs_per_day:
        return False, f"daily limit reached ({src.max_runs_per_day} run(s) per day)"
    return True, ""


def record_run(src: Source, now: datetime | None = None) -> None:
    now = now or utcnow()
    refresh(src, now)
    src.runs_today += 1
    src.last_run_at = now


def record_success(src: Source, message: str) -> None:
    src.status, src.consecutive_errors, src.last_error, src.last_result = "ok", 0, "", message


def record_failure(session: Session, src: Source, error: Exception, now: datetime | None = None) -> None:
    now = now or utcnow()
    src.consecutive_errors += 1
    src.last_error = str(error)
    label = SOURCE_DEFAULTS.get(src.key, (src.key,))[0]
    if isinstance(error, RateLimited) or src.consecutive_errors >= ERRORS_BEFORE_PAUSE:
        src.status, src.paused_until = "paused", now + PAUSE
        why = f"the site answered {error}" if isinstance(error, RateLimited) else f"{src.consecutive_errors} errors in a row ({error})"
        src.last_error = f"Paused for 24 h: {why}"
        notify(session, "source_paused", f"{label} paused for 24 hours: {why}.", "/settings?section=sources")
    else:
        src.status = "error"


def resume(src: Source) -> None:
    src.status, src.paused_until, src.consecutive_errors, src.last_error = "ok", None, 0, ""
