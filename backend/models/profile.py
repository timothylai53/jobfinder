from datetime import date

from sqlmodel import Field, SQLModel

from models._base import json_col


class ProfileBase(SQLModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""  # printed as links in the resume / cover-letter header; never put in AI prompts
    github_url: str = ""
    portfolio_url: str = ""
    location: str = ""
    years_of_experience: float = 0
    years_confirmed: bool = False  # I have saved this value myself (0 can be a real answer)
    education_level: str = ""  # SPM / STPM / Diploma / Degree / Master / PhD
    education_field: str = ""
    degree_status: str = "completed"  # completed / in_progress
    expected_graduation: date | None = None
    languages: list[str] = Field(default_factory=list, sa_column=json_col())
    preferred_locations: list[str] = Field(default_factory=list, sa_column=json_col())
    remote_ok: bool = True
    skills: list[str] = Field(default_factory=list, sa_column=json_col())
    notes: str = ""


class Profile(ProfileBase, table=True):
    id: int | None = Field(default=1, primary_key=True)
