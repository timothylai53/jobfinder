from datetime import date, datetime

from sqlmodel import Field, SQLModel

from models._base import json_col, utcnow


class SearchProfileBase(SQLModel):
    name: str
    keywords: list[str] = Field(default_factory=list, sa_column=json_col())
    locations: list[str] = Field(default_factory=list, sa_column=json_col())  # "Remote" allowed
    job_type: str = "fulltime"  # fulltime / parttime / contract / internship / "" (any)
    days: int = 7  # posted within the last N days
    sources: list[str] = Field(default_factory=list, sa_column=json_col())  # empty = every enabled source
    max_results: int = 0  # per source per run; 0 = the source's own limit
    enabled: bool = True


class SearchProfile(SearchProfileBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class Source(SQLModel, table=True):
    """One job site. Health and safety limits live here."""
    key: str = Field(primary_key=True)  # jobstreet / linkedin / indeed / glassdoor
    enabled: bool = True
    status: str = "ok"  # ok / error / paused
    paused_until: datetime | None = None
    last_run_at: datetime | None = None
    last_error: str = ""
    last_result: str = ""
    runs_today: int = 0
    runs_date: date | None = None
    consecutive_errors: int = 0
    max_results: int = 50  # per run
    max_runs_per_day: int = 2


class Automation(SQLModel, table=True):
    key: str = Field(primary_key=True)
    enabled: bool = False
    mode: str = "scheduled"  # scheduled / manual
    schedule: str = ""  # "09:00" (daily) or "after:fetch_jobs"
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None


class AutomationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    automation_key: str = Field(index=True)
    trigger: str = "manual"  # manual / schedule / catch-up / chain
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    result: str = "running"  # running / ok / error / skipped
    items_processed: int = 0
    message: str = ""
    error: str = ""
    # fetch_jobs only: one dict per source (source, status, profiles, cap, fetched, new, merged, hidden, requests,
    # notes, error), so the run log can show aligned numbers instead of parsing the message.
    details: list[dict] = Field(default_factory=list, sa_column=json_col())
