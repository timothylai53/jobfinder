"""Resume upload -> draft (not saved) -> reviewed import into Profile + Experience Bank."""
import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import UPLOADS_DIR
from app.db import get_session
from app.settings_store import next_item_code
from matcher.service import get_profile, rescore_all
from models import BaseResume, ExperienceItem, ExperienceItemBase
from resume_parser.extract_text import UnsupportedFile, extract_text
from resume_parser.sections import parse_resume_text
from skills.service import build_matcher

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
MAX_UPLOAD = 10 * 1024 * 1024


@router.post("/parse")
async def parse_upload(file: UploadFile = File(...), session: Session = Depends(get_session)):
    name = file.filename or "resume"
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(422, "Upload a .pdf or .docx file")
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 10 MB")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[-80:]
    path = UPLOADS_DIR / f"{uuid.uuid4().hex[:8]}_{safe}"
    path.write_bytes(data)
    try:
        text = extract_text(path)
    except UnsupportedFile as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # corrupted / encrypted files
        raise HTTPException(422, f"Could not read this file: {e.__class__.__name__}") from e
    if not text.strip():
        raise HTTPException(422, "No text found in the file (is it a scanned image?). Add items manually instead.")
    draft = parse_resume_text(text, build_matcher(session))
    # Items that are already in the bank (same type, title, organization and dates) are marked so the
    # review screen can skip them by default.
    existing = {item_key(i.type, i.title, i.organization, i.start, i.end): i.code
                for i in session.exec(select(ExperienceItem)).all()}
    for it in draft["items"]:
        it["duplicate_of"] = existing.get(item_key(it["type"], it["title"], it["organization"], it["start"], it["end"]))
    # draft["raw_text"] has the References section removed: referee details are never stored.
    return {"file_path": str(path), "suggested_name": name.rsplit(".", 1)[0], **draft}


def item_key(type_: str, title: str, org: str, start: str, end: str) -> tuple:
    sq = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()
    return (sq(type_), sq(title), sq(org), sq(start), sq(end))


def _check_name_free(session: Session, name: str, exclude_id: int | None = None) -> None:
    for r in session.exec(select(BaseResume)).all():
        if r.id != exclude_id and r.name.strip().lower() == name.strip().lower():
            raise HTTPException(409, f"A BaseResume called “{r.name}” already exists. Choose another name.")


class ProfileUpdates(BaseModel):
    """Only the fields I ticked in the review screen are sent."""
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    education_level: str | None = None
    education_field: str | None = None
    degree_status: str | None = None
    expected_graduation: date | None = None
    languages: list[str] | None = None
    skills: list[str] | None = None


class ImportRequest(BaseModel):
    name: str
    file_path: str = ""
    raw_text: str = ""
    profile: ProfileUpdates = ProfileUpdates()
    items: list[ExperienceItemBase] = []


@router.post("/import")
def import_resume(req: ImportRequest, session: Session = Depends(get_session)):
    _check_name_free(session, req.name.strip() or "Resume")
    resume = BaseResume(name=req.name.strip() or "Resume", original_file_path=req.file_path, raw_text=req.raw_text)
    session.add(resume)
    session.flush()
    p = get_profile(session)
    for k, v in req.profile.model_dump(exclude_unset=True).items():
        if k in ("languages", "skills"):
            v = list(dict.fromkeys([*getattr(p, k), *(v or [])]))  # merge, never drop existing
        setattr(p, k, v)
    session.add(p)
    codes = []
    for it in req.items:
        item = ExperienceItem(**it.model_dump(exclude={"resume_ids"}), resume_ids=[resume.id], code=next_item_code(session))
        session.add(item)
        codes.append(item.code)
    session.commit()
    rescore_all(session)
    return {"resume_id": resume.id, "item_codes": codes}


class ResumeOut(BaseModel):
    id: int
    name: str
    original_file_path: str
    created_at: str
    item_ids: list[int]


@router.get("", response_model=list[ResumeOut])
def list_resumes(session: Session = Depends(get_session)):
    items = session.exec(select(ExperienceItem)).all()
    return [
        ResumeOut(id=r.id, name=r.name, original_file_path=r.original_file_path, created_at=r.created_at.isoformat(),
                  item_ids=[i.id for i in items if r.id in i.resume_ids])
        for r in session.exec(select(BaseResume).order_by(BaseResume.id)).all()
    ]


class ResumeUpdate(BaseModel):
    name: str
    item_ids: list[int]


@router.put("/{resume_id}")
def update_resume(resume_id: int, req: ResumeUpdate, session: Session = Depends(get_session)):
    r = session.get(BaseResume, resume_id)
    if not r:
        raise HTTPException(404, "Resume not found")
    if req.name.strip():
        _check_name_free(session, req.name, resume_id)
    r.name = req.name.strip() or r.name
    wanted = set(req.item_ids)
    for i in session.exec(select(ExperienceItem)).all():
        has = resume_id in i.resume_ids
        if i.id in wanted and not has:
            i.resume_ids = [*i.resume_ids, resume_id]
        elif i.id not in wanted and has:
            i.resume_ids = [x for x in i.resume_ids if x != resume_id]
    session.commit()
    return {"ok": True}


@router.post("")
def create_resume(req: ResumeUpdate, session: Session = Depends(get_session)):
    _check_name_free(session, req.name.strip() or "Resume")
    r = BaseResume(name=req.name.strip() or "Resume")
    session.add(r)
    session.flush()
    for i in session.exec(select(ExperienceItem)).all():
        if i.id in req.item_ids:
            i.resume_ids = [*i.resume_ids, r.id]
    session.commit()
    return {"id": r.id}


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, session: Session = Depends(get_session)):
    """Deletes the BaseResume selection only; bank items stay (the bank is the source of truth)."""
    r = session.get(BaseResume, resume_id)
    if not r:
        raise HTTPException(404, "Resume not found")
    for i in session.exec(select(ExperienceItem)).all():
        if resume_id in i.resume_ids:
            i.resume_ids = [x for x in i.resume_ids if x != resume_id]
    session.delete(r)
    session.commit()
    return {"ok": True}
