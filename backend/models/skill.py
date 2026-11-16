from sqlmodel import Field, SQLModel

from models._base import json_col


class SkillBase(SQLModel):
    name: str = Field(index=True, unique=True)
    category: str = "other"
    aliases: list[str] = Field(default_factory=list, sa_column=json_col())


class Skill(SkillBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
