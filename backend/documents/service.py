"""Saving document versions. Only content I accepted in the review screen arrives here.

A resume version snapshots each bank item's header (type, title, organization, dates) at save time, so an old
version still renders the same after the bank changes. Every resume item must point at a real bank item:
an unknown or missing ID can't be saved (the fabrication guard already flagged it in red).
"""
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session, func, select

from matcher.service import get_profile
from models import AITask, Document, ExperienceItem, Job, MatchResult
from models._base import require_id

# Section order on the page; anything else the AI named goes after these, in its order.
SECTION_ORDER = ["Summary", "Skills", "Experience", "Projects", "Education", "Certifications", "Publications", "Achievements"]
DEFAULT_SECTION = {"work": "Experience", "project": "Projects", "education": "Education",
                   "certification": "Certifications", "publication": "Publications", "achievement": "Achievements"}


class DocumentError(Exception):
    pass


class AcceptedItem(BaseModel):
    source_id: str
    text: str


class AcceptedSection(BaseModel):
    section: str
    items: list[AcceptedItem]


DocumentSource = Literal["copy_paste", "ollama", "template", "manual"]


class ResumeIn(BaseModel):
    job_id: int
    source: DocumentSource = "copy_paste"
    ai_task_id: int | None = None
    summary: str = ""
    skills: list[str] = []
    sections: list[AcceptedSection] = []
    add_original_ids: list[str] = []  # bank items the AI left out that I chose to include as they are


class CoverLetterIn(BaseModel):
    job_id: int
    source: DocumentSource = "copy_paste"
    ai_task_id: int | None = None
    greeting: str
    paragraphs: list[str]
    closing: str
    used_ids: list[str] = []


def next_version(session: Session, job_id: int | None, type_: str) -> int:
    q = select(func.max(Document.version)).where(Document.type == type_, Document.job_id == job_id)
    return (session.exec(q).one() or 0) + 1


def _save(session: Session, job_id: int | None, type_: str, content: dict, source: str, ai_task_id: int | None) -> Document:
    doc = Document(job_id=job_id, type=type_, version=next_version(session, job_id, type_), content=content,
                   source=source, ai_task_id=ai_task_id)
    session.add(doc)
    session.flush()
    if ai_task_id:
        t = session.get(AITask, ai_task_id)
        if t is not None:
            t.status, t.document_id = "saved", doc.id
    session.commit()
    session.refresh(doc)
    return doc


def link(url: str) -> dict | None:
    """A profile URL -> {"href", "text"} for the header. The visible text is the plain address without
    "https://" or "www." (readable, and what an ATS keeps); anything that isn't a web address is left out."""
    url = (url or "").strip()
    if not url or any(c.isspace() for c in url):
        return None
    m = re.match(r"^([a-z][a-z0-9+.-]*):", url, re.I)
    if m and m.group(1).lower() not in ("http", "https"):
        return None  # javascript:, mailto: ...
    href = url if m else f"https://{url}"
    text = re.sub(r"^https?://(www\.)?", "", href, flags=re.I).rstrip("/")
    return {"href": href, "text": text} if "." in text else None


def _header(session: Session) -> dict:
    p = get_profile(session)
    links = [link(u) for u in (p.linkedin_url, p.github_url, p.portfolio_url)]
    return {"name": p.name, "email": p.email, "phone": p.phone, "location": p.location,
            "links": [x for x in links if x]}


def _job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise DocumentError("Job not found")
    return job


def _entry(item: ExperienceItem, section: str) -> dict:
    return {"source_id": item.code, "type": item.type, "title": item.title, "organization": item.organization,
            "start": item.start, "end": item.end, "section": section, "bullets": []}


def save_resume(session: Session, data: ResumeIn) -> Document:
    job = _job(session, data.job_id)
    bank = {i.code.upper(): i for i in session.exec(select(ExperienceItem)).all()}
    entries: dict[str, dict] = {}  # one entry per bank item, bullets in accepted order
    order: list[str] = []
    for sec in data.sections:
        for it in sec.items:
            code = it.source_id.strip().upper()
            if code not in bank:
                raise DocumentError(f"“{it.text[:60]}” has source ID {it.source_id!r}, which is not in your Experience "
                                    "Bank. Fix the ID or reject the item before saving.")
            if code not in entries:
                entries[code] = _entry(bank[code], sec.section.strip() or DEFAULT_SECTION.get(bank[code].type, "Other"))
                order.append(code)
            text = it.text.strip()
            if text and text != bank[code].title.strip():
                entries[code]["bullets"].append(text)
    for raw in data.add_original_ids:
        code = raw.strip().upper()
        if code in bank and code not in entries:
            item = bank[code]
            entries[code] = {**_entry(item, DEFAULT_SECTION.get(item.type, "Other")), "bullets": list(item.bullets)}
            order.append(code)
    if not entries and not data.summary.strip():
        raise DocumentError("Nothing was accepted, so there is no resume to save.")
    sections: list[dict] = []
    for code in order:
        e = entries[code]
        group = next((s for s in sections if s["section"] == e["section"]), None)
        if group is None:
            group = {"section": e["section"], "entries": []}
            sections.append(group)
        group["entries"].append({k: v for k, v in e.items() if k != "section"})
    rank = {name: i for i, name in enumerate(SECTION_ORDER)}
    sections.sort(key=lambda s: rank.get(s["section"], len(rank)))
    content = {"header": _header(session), "target": {"title": job.title, "company": job.company},
               "summary": data.summary.strip(), "skills": [s.strip() for s in data.skills if s.strip()],
               "sections": sections}
    return _save(session, job.id, "resume", content, data.source, data.ai_task_id)


def save_cover_letter(session: Session, data: CoverLetterIn) -> Document:
    job = _job(session, data.job_id)
    paragraphs = [p.strip() for p in data.paragraphs if p.strip()]
    if not paragraphs:
        raise DocumentError("The cover letter has no paragraphs.")
    content = {"header": _header(session), "date": date.today().strftime("%d %B %Y").lstrip("0"),
               "company": job.company, "role": job.title, "greeting": data.greeting.strip() or "Dear Hiring Manager,",
               "paragraphs": paragraphs, "closing": data.closing.strip() or "Sincerely,",
               "used_ids": [c.strip().upper() for c in data.used_ids if c.strip()]}
    return _save(session, job.id, "cover_letter", content, data.source, data.ai_task_id)


def save_analysis(session: Session, job_id: int, type_: str, content: dict, source: str, ai_task_id: int | None,
                  flags: list | None = None) -> Document:
    """Deep analysis / interview prep: saved as they are (with the guard's flags kept alongside)."""
    job = _job(session, job_id)
    doc = _save(session, job.id, type_, {**content, "flags": flags or []}, source, ai_task_id)
    if type_ == "deep_analysis":  # brief §5: MatchResult method "deep", next to the quick score
        for old in session.exec(select(MatchResult).where(MatchResult.job_id == job.id, MatchResult.method == "deep")).all():
            session.delete(old)
        session.add(MatchResult(job_id=require_id(job), total=int(content.get("overall_fit", 0)), method="deep",
                                breakdown={**content, "document_id": doc.id}, gate_flags=[]))
        session.commit()
        session.refresh(doc)  # the commit expired it
    return doc
