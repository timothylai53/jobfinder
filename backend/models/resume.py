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
