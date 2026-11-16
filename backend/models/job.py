from datetime import date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from models._base import json_col, utcnow


class JobBase(SQLModel):
    title: str
    company: str = ""
    location: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    job_type: str = ""
    work_arrangement: str = ""  # Hybrid / Remote / On-site, when the posting says
    posted_date: date | None = None
    urls: list[str] = Field(default_factory=list, sa_column=json_col())
    sources: list[str] = Field(default_factory=list, sa_column=json_col())
    description: str = ""


class Job(JobBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    fetched_at: datetime = Field(default_factory=utcnow)
    dedupe_key: str = Field(default="", index=True)
    hidden: bool = False
    hidden_reason: str = ""
    hidden_by: str = ""  # "" / "rule" / "manual"
    # Site job IDs, e.g. {"jobstreet": "95667394"}: used to never re-fetch a stored job's details
    external_ids: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, default=dict))
    high_match_notified: bool = False


class MatchResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True, ondelete="CASCADE")
    total: int
    breakdown: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    gate_flags: list[str] = Field(default_factory=list, sa_column=json_col())
    scored_at: datetime = Field(default_factory=utcnow)
    method: str = "quick"
