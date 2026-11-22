"""AI: settings, Ollama status, prompt templates, and the task flow (prompt -> reply -> validate -> review)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from ai import ollama, service
from ai import prompt_templates as templates
from ai.schemas import TASKS
from app.db import engine, get_session
from app.settings_store import AISettings, get_ai, set_ai
from models import AITask
from models._base import require_id

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---------- settings ----------

@router.get("/settings", response_model=AISettings)
def read_settings(session: Session = Depends(get_session)):
    return get_ai(session)


@router.put("/settings", response_model=AISettings)
def update_settings(data: AISettings, session: Session = Depends(get_session)):
    set_ai(session, data)
    return get_ai(session)


@router.get("/ollama/status")
def ollama_status(model: str | None = None, session: Session = Depends(get_session)):
    """Only ever contacts the local Ollama API."""
    return ollama.status(model or get_ai(session).ollama_model)


# ---------- prompt templates ----------

def _template_out(name: str) -> dict:
    return {"name": name, "text": templates.load(name), "edited": templates.is_edited(name),
            "placeholders": list(templates.required_placeholders(name))}


@router.get("/templates")
def list_templates():
    return [_template_out(n) for n in templates.NAMES]


class TemplateIn(BaseModel):
    text: str


@router.put("/templates/{name}")
def save_template(name: str, data: TemplateIn):
    if name not in templates.NAMES:
        raise HTTPException(404, "Unknown template")
    if not data.text.strip():
        raise HTTPException(422, "The template is empty. Use Reset to go back to the default.")
    templates.save(name, data.text)
    return _template_out(name)


@router.post("/templates/{name}/reset")
def reset_template(name: str):
    if name not in templates.NAMES:
        raise HTTPException(404, "Unknown template")
    templates.reset(name)
    return _template_out(name)


# ---------- tasks ----------

class TaskIn(BaseModel):
    task: str
    job_id: int | None = None
    resume_text: str = ""
    provider: str | None = None  # None = the global AI mode; per-action override (brief §6.6)
    base_resume_id: int | None = None  # tailor_resume only: use just this base resume's items


@router.post("/tasks", response_model=AITask)
def create_task(data: TaskIn, session: Session = Depends(get_session)):
    if data.task not in TASKS:
        raise HTTPException(422, f"task must be one of {', '.join(TASKS)}")
    try:
        t = service.create(session, data.task, data.job_id, data.resume_text, data.provider, data.base_resume_id)
    except service.AIUnavailable as e:
        raise HTTPException(409, str(e)) from e
    if t.provider == "ollama":
        service.run_ollama_in_background(engine, require_id(t))
    return t


def _task(session: Session, task_id: int) -> AITask:
    t = session.get(AITask, task_id)
    if t is None:
        raise HTTPException(404, "AI task not found")
    return t


@router.get("/tasks/{task_id}", response_model=AITask)
def get_task(task_id: int, session: Session = Depends(get_session)):
    return _task(session, task_id)


class ReplyIn(BaseModel):
    reply: str


@router.post("/tasks/{task_id}/reply", response_model=AITask)
def submit_reply(task_id: int, data: ReplyIn, session: Session = Depends(get_session)):
    return service.submit_reply(session, _task(session, task_id), data.reply)


class EditedIn(BaseModel):
    data: dict


@router.post("/tasks/{task_id}/edited", response_model=AITask)
def submit_edited(task_id: int, body: EditedIn, session: Session = Depends(get_session)):
    return service.submit_edited(session, _task(session, task_id), body.data)


@router.get("/tasks/{task_id}/fixup")
def fixup(task_id: int, session: Session = Depends(get_session)):
    t = _task(session, task_id)
    if not t.response.strip():
        raise HTTPException(409, "There is no reply to fix yet")
    return {"prompt": service.fixup_prompt(t)}


@router.post("/tasks/{task_id}/run-ollama", response_model=AITask)
def rerun_ollama(task_id: int, session: Session = Depends(get_session)):
    t = _task(session, task_id)
    if get_ai(session).mode == "off":
        raise HTTPException(409, "AI is switched off in Settings")
    t.provider, t.status = "ollama", "running"
    session.add(t)
    session.commit()
    service.run_ollama_in_background(engine, require_id(t))
    session.refresh(t)
    return t
