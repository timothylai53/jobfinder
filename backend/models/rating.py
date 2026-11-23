from datetime import datetime

from sqlmodel import Field, SQLModel

from models._base import utcnow

RATINGS = ("too_high", "about_right", "too_low")


class ScoreRating(SQLModel, table=True):
    """My own verdict on a job's quick score ("does this score feel right?"), to measure how often the score agrees
    with me. One per job; deleted with the job."""
    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True, unique=True, ondelete="CASCADE")
    rating: str  # too_high / about_right / too_low
    note: str = ""
    score_at: int | None = None  # the score when I rated it (scores change when rules or the profile change)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
