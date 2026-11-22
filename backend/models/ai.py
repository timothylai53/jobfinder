from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from models._base import json_col, utcnow

DOCUMENT_TYPES = ("resume", "cover_letter", "interview_prep", "deep_analysis")
DOCUMENT_SOURCES = ("copy_paste", "ollama", "template", "manual")


class AITask(SQLModel, table=True):
    """One AI request: the prompt, the reply, and what the parser / fabrication guard made of it."""
    id: int | None = Field(default=None, primary_key=True)
    task: str  # parse_resume / deep_analysis / tailor_resume / cover_letter / interview_prep
    job_id: int | None = Field(default=None, foreign_key="job.id", index=True, ondelete="CASCADE")
    provider: str = "copy_paste"  # copy_paste / ollama
    status: str = "waiting"  # waiting (for a pasted reply) / running (Ollama) / parsed / invalid / failed / saved
    prompt: str = ""
    source_text: str = ""  # parse_resume: the resume text the reply is checked against
    response: str = ""
    errors: list = Field(default_factory=list, sa_column=json_col())  # [{"path", "message"}]
    flags: list = Field(default_factory=list, sa_column=json_col())  # fabrication guard
    repairs: list = Field(default_factory=list, sa_column=json_col())
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    error_message: str = ""  # provider failures (Ollama not running, model missing, timeout)
    document_id: int | None = None
    base_resume_id: int | None = None  # tailor_resume: the prompt held only this base resume's items
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Document(SQLModel, table=True):
    """A numbered version of a resume / cover letter / interview prep / deep analysis for one job."""
    id: int | None = Field(default=None, primary_key=True)
    job_id: int | None = Field(default=None, foreign_key="job.id", index=True, ondelete="CASCADE")
    type: str
    version: int
    content: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    pdf_path: str = ""
    source: str = "manual"  # copy_paste / ollama / template / manual
    ai_task_id: int | None = None
    created_at: datetime = Field(default_factory=utcnow)
