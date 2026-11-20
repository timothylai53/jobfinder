"""Output schemas for every AI task (brief §6.6, minimum fields). Lists default to empty so a reply that
leaves out an optional list still validates; required fields have no default."""
from typing import Literal

from pydantic import BaseModel, Field

TASKS = ("parse_resume", "deep_analysis", "tailor_resume", "cover_letter", "interview_prep")


class Requirement(BaseModel):
    text: str
    type: Literal["required", "preferred"]
    status: Literal["met", "partial", "not_met"]
    evidence_ids: list[str] = []
    note: str = ""


class DeepAnalysis(BaseModel):
    requirements: list[Requirement]
    overall_fit: int = Field(ge=0, le=100)
    strengths: list[str] = []
    gaps: list[str] = []
    resume_suggestions: list[str] = []


class TailorItem(BaseModel):
    source_id: str = ""  # a missing ID is allowed by the schema but flagged by the fabrication guard
    text: str


class TailorSection(BaseModel):
    section: str
    items: list[TailorItem]


class TailorResume(BaseModel):
    summary: str = ""
    skills_order: list[str] = []
    sections: list[TailorSection]
    omitted_ids: list[str] = []
    notes: str = ""


class CoverLetter(BaseModel):
    greeting: str
    paragraphs: list[str] = Field(min_length=1)
    closing: str
    used_ids: list[str] = []


class InterviewQuestion(BaseModel):
    question: str
    category: str = ""
    why_likely: str = ""
    suggested_points_ids: list[str] = []


class InterviewPrep(BaseModel):
    questions: list[InterviewQuestion] = Field(min_length=1)


class ParsedProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    education_level: str = ""
    education_field: str = ""
    languages: list[str] = []
    skills: list[str] = []


class ParsedItem(BaseModel):
    type: Literal["work", "project", "education", "achievement", "certification", "publication"]
    title: str
    organization: str = ""
    start: str = ""
    end: str = ""
    bullets: list[str] = []
    skills: list[str] = []


class ParseResume(BaseModel):
    profile: ParsedProfile = ParsedProfile()
    items: list[ParsedItem]


SCHEMAS: dict[str, type[BaseModel]] = {
    "parse_resume": ParseResume,
    "deep_analysis": DeepAnalysis,
    "tailor_resume": TailorResume,
    "cover_letter": CoverLetter,
    "interview_prep": InterviewPrep,
}

# Compact examples shown in every prompt (small models follow an example better than a JSON Schema).
# tests/test_ai_parser.py checks each one validates against its schema.
EXAMPLES: dict[str, str] = {
    "parse_resume": """{
  "profile": {"name": "", "email": "", "phone": "", "location": "", "education_level": "Degree",
              "education_field": "Software Engineering", "languages": ["English"], "skills": ["Python"]},
  "items": [
    {"type": "project", "title": "Inventory App", "organization": "University project", "start": "Jan 2024",
     "end": "May 2024", "bullets": ["Built a REST API in Python"], "skills": ["Python"]}
  ]
}""",
    "deep_analysis": """{
  "requirements": [
    {"text": "2+ years of Java", "type": "required", "status": "partial", "evidence_ids": ["B3"],
     "note": "Java used in one project, not 2 years of work"}
  ],
  "overall_fit": 55,
  "strengths": ["..."],
  "gaps": ["..."],
  "resume_suggestions": ["..."]
}""",
    "tailor_resume": """{
  "summary": "...",
  "skills_order": ["Python", "SQL"],
  "sections": [
    {"section": "Experience", "items": [
      {"source_id": "B2", "text": "One rewritten bullet from B2, without its title, organization or dates"},
      {"source_id": "B2", "text": "A second bullet from B2, as its own item"}
    ]},
    {"section": "Projects", "items": [{"source_id": "B3", "text": "Rewritten bullet based only on B3"}]},
    {"section": "Certifications", "items": [{"source_id": "B7", "text": "Certificate name from B7"}]}
  ],
  "omitted_ids": ["B5"],
  "notes": "..."
}""",
    "cover_letter": """{
  "greeting": "Dear Hiring Manager,",
  "paragraphs": ["...", "..."],
  "closing": "Sincerely,",
  "used_ids": ["B3", "B4"]
}""",
    "interview_prep": """{
  "questions": [
    {"question": "...", "category": "technical", "why_likely": "...", "suggested_points_ids": ["B3"]}
  ]
}""",
}
