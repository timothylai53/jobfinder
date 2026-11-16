"""Document versions: save accepted content, list per job, HTML preview, PDF download, template cover letter."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.settings_store import get_general
from documents import cover_template, render
from documents.service import CoverLetterIn, DocumentError, ResumeIn, save_analysis, save_cover_letter, save_resume
from models import AITask, Application, Document, Job

router = APIRouter(prefix="/api", tags=["documents"])


def _out(doc: Document) -> dict:
    return {**doc.model_dump(), "has_pdf": bool(doc.pdf_path), "printable": doc.type in render.RENDERABLE}


@router.get("/jobs/{job_id}/documents")
def list_documents(job_id: int, session: Session = Depends(get_session)):
    docs = session.exec(select(Document).where(Document.job_id == job_id)
                        .order_by(Document.type, Document.version.desc())).all()
    return [_out(d) for d in docs]


def _doc(session: Session, doc_id: int) -> Document:
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, session: Session = Depends(get_session)):
    return _out(_doc(session, doc_id))


@router.post("/documents/resume")
def create_resume(data: ResumeIn, session: Session = Depends(get_session)):
    try:
        return _out(save_resume(session, data))
    except DocumentError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/documents/cover-letter")
def create_cover_letter(data: CoverLetterIn, session: Session = Depends(get_session)):
    try:
        return _out(save_cover_letter(session, data))
    except DocumentError as e:
        raise HTTPException(422, str(e)) from e


class TemplateDraftIn(BaseModel):
    job_id: int
    item_codes: list[str] | None = None  # None = suggest the best 1-2 bank items


@router.post("/documents/cover-letter/template-draft")
def cover_letter_template(data: TemplateDraftIn, session: Session = Depends(get_session)):
    """Fill-in-the-blanks draft (not saved). Works with AI off."""
    job = session.get(Job, data.job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {**cover_template.draft(session, job, data.item_codes),
            "suggested_ids": cover_template.suggest_items(session, job)}


class AnalysisIn(BaseModel):
    ai_task_id: int


@router.post("/documents/from-task")
def save_task_result(data: AnalysisIn, session: Session = Depends(get_session)):
    """Deep analysis / interview prep: the validated result is saved as a new version."""
    t = session.get(AITask, data.ai_task_id)
    if t is None or t.result is None:
        raise HTTPException(409, "This AI task has no valid result to save")
    if t.task not in ("deep_analysis", "interview_prep") or t.job_id is None:
        raise HTTPException(422, "Only deep analysis and interview prep are saved this way")
    try:
        doc = save_analysis(session, t.job_id, t.task, t.result, t.provider, t.id, t.flags)
    except DocumentError as e:
        raise HTTPException(422, str(e)) from e
    return _out(doc)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, session: Session = Depends(get_session)):
    doc = _doc(session, doc_id)
    for app in session.exec(select(Application).where(Application.job_id == doc.job_id)).all():
        if doc.id in (app.resume_version_id, app.cover_letter_version_id):
            raise HTTPException(409, "This version is recorded as sent with your application. Unlink it first.")
    session.delete(doc)
    session.commit()
    return {"ok": True}


@router.get("/documents/{doc_id}/html", response_class=HTMLResponse)
def preview_html(doc_id: int, session: Session = Depends(get_session)):
    doc = _doc(session, doc_id)
    if doc.type not in render.RENDERABLE:
        raise HTTPException(422, "Only resumes and cover letters have a printable layout")
    return HTMLResponse(render.html_for(doc, get_general(session).resume_projects_first))


@router.get("/documents/{doc_id}/pdf")
def download_pdf(doc_id: int, session: Session = Depends(get_session)):
    """Renders the PDF (Playwright, offline) and stores it under data/documents/<job_id>/. It is rendered again on
    every download, so layout settings (section order) and layout fixes reach older versions too; the content
    itself is the saved version and never changes."""
    doc = _doc(session, doc_id)
    if doc.type not in render.RENDERABLE:
        raise HTTPException(422, "Only resumes and cover letters can be exported to PDF")
    try:
        html = render.html_for(doc, get_general(session).resume_projects_first)
        path = render.html_to_pdf(html, render.pdf_path_for(doc))
    except render.PdfUnavailable as e:
        raise HTTPException(503, str(e)) from e
    if doc.pdf_path != str(path):
        doc.pdf_path = str(path)
        session.add(doc)
        session.commit()
    return FileResponse(path, media_type="application/pdf", filename=path.name)
