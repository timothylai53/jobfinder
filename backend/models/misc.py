from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from models._base import utcnow


class Notification(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    type: str
    message: str
    link: str = ""
    read: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: dict | list | str | int | float | bool | None = Field(default=None, sa_column=Column(JSON))
