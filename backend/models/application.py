from datetime import date, datetime

from sqlmodel import Field, SQLModel

from models._base import utcnow

STATUSES = ("Saved", "Applied", "Interview", "Offer", "Rejected", "Withdrawn")


class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", unique=True, ondelete="CASCADE")
    status: str = "Saved"
    applied_at: date | None = None
    follow_up_at: date | None = None
    notes: str = ""
    resume_version_id: int | None = None
    cover_letter_version_id: int | None = None
    reminded_on: date | None = None  # the follow-up date that has already been reminded
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StatusHistory(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="application.id", index=True, ondelete="CASCADE")
    from_status: str | None = None
    to_status: str
    changed_at: datetime = Field(default_factory=utcnow)
