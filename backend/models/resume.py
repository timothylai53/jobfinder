from datetime import datetime

from sqlmodel import Field, SQLModel

from models._base import json_col, utcnow


class BaseResume(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    original_file_path: str = ""
    raw_text: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None  # last rename or change of its item selection
    last_used_at: datetime | None = None  # last time a resume was tailored from it


def date_parts(start: str, end: str) -> list[str]:
    """The dates to print for an item: ["2024"] for 2024-2024 (any case or spacing), else the non-empty ones."""
    s, e = (start or "").strip(), (end or "").strip()
    if s and e and " ".join(s.lower().split()) == " ".join(e.lower().split()):
        return [s]
    return [d for d in (s, e) if d]


class ExperienceItemBase(SQLModel):
    type: str = "work"  # work / project / education / achievement / certification
    title: str = ""
    organization: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = Field(default_factory=list, sa_column=json_col())
    skills: list[str] = Field(default_factory=list, sa_column=json_col())
    resume_ids: list[int] = Field(default_factory=list, sa_column=json_col())


class ExperienceItem(ExperienceItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)  # stable short ID, e.g. B12
    created_at: datetime = Field(default_factory=utcnow)
