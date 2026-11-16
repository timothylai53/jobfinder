"""AI task lifecycle, shared by both providers:

create (prompt built) -> reply (pasted by me, or returned by Ollama) -> tolerant parse + schema validation ->
fabrication guard -> I review -> save as a Document version (documents/service.py).
"""
import threading

from sqlmodel import Session, select

from ai import guard, ollama, prompts
from ai.parser import parse_reply, validate
from ai.schemas import TASKS
from app.settings_store import get_ai
from matcher.service import build_candidate, get_profile
from models import AITask, ExperienceItem, Job
from models._base import utcnow
from skills.service import build_matcher


class AIUnavailable(Exception):
    """AI is switched off, or the request doesn't make sense (unknown task, missing job)."""


def facts(session: Session) -> guard.Facts:
    matcher = build_matcher(session)
    cand = build_candidate(session, matcher)
    items = session.exec(select(ExperienceItem)).all()
    p = get_profile(session)
    grad = f"{p.expected_graduation:%B %Y}" if p.expected_graduation else ""
    years = f"{p.years_of_experience:g} years" if p.years_confirmed or p.years_of_experience else ""
    profile_text = "\n".join([p.location, years, p.education_level, p.education_field, grad,
                              *p.languages, *p.skills, p.notes])
    return guard.Facts(
        codes={i.code.upper() for i in items}, skills=set(cand.skill_evidence), matcher=matcher,
        item_types={i.code.upper(): i.type for i in items},
        item_skills={i.code.upper(): {s for s, src in cand.skill_evidence.items() if i.code in src} for i in items},
        item_text={i.code.upper(): "\n".join([i.title, i.organization, i.start, i.end, *i.bullets, *i.skills])
                   for i in items},
        profile_text=profile_text,
        item_headers={i.code.upper(): [i.title, i.organization, i.start, i.end] for i in items})


def create(session: Session, task: str, job_id: int | None = None, resume_text: str = "",
           provider: str | None = None) -> AITask:
    cfg = get_ai(session)
    if cfg.mode == "off":
        raise AIUnavailable("AI is switched off in Settings. The template cover letter still works.")
    if task not in TASKS:
        raise AIUnavailable(f"Unknown AI task {task!r}")
    provider = provider or cfg.mode
    if provider not in ("copy_paste", "ollama"):
        raise AIUnavailable(f"Unknown provider {provider!r}")
    job = None
    if task != "parse_resume":
        job = session.get(Job, job_id) if job_id else None
        if job is None:
            raise AIUnavailable("Job not found")
    elif not resume_text.strip():
        raise AIUnavailable("There is no resume text to parse")
    t = AITask(task=task, job_id=job.id if job else None, provider=provider,
               status="running" if provider == "ollama" else "waiting",
               prompt=prompts.build(session, task, job, resume_text), source_text=resume_text)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _store(session: Session, t: AITask, ok: bool, data: dict | None, errors: list, repairs: list) -> AITask:
    t.errors, t.repairs = errors, repairs
    flags: list[dict] = []
    if ok and data is not None:
        f = facts(session)
        if t.task == "tailor_resume":  # strips a repeated item header in place, before the other checks
            flags += guard.tidy_tailor(data, f)
        flags += guard.check(t.task, data, f, t.source_text)
    t.result = data if ok else None
    t.flags = flags
    t.status = "parsed" if ok else "invalid"
    t.error_message = ""
    t.updated_at = utcnow()
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def submit_reply(session: Session, t: AITask, reply: str, provider: str = "copy_paste") -> AITask:
    """A reply I pasted is Copy-Paste by definition, even if the task started on Ollama (which then failed)."""
    t.response, t.provider = reply, provider
    out = parse_reply(t.task, reply)
    return _store(session, t, out.ok, out.data, out.errors, out.repairs)


def submit_edited(session: Session, t: AITask, data: dict) -> AITask:
    """I fixed the JSON by hand in the review screen: validate it and run the guard again."""
    model, errors = validate(t.task, data)
    return _store(session, t, model is not None, model.model_dump() if model else None, errors, [])


def fixup_prompt(t: AITask) -> str:
    return prompts.fixup(t.task, t.response, t.errors or [{"path": "(reply)", "message": "the reply did not match the format"}])


# ---------- Ollama ----------

def run_ollama(engine, task_id: int) -> None:
    """Send the task's prompt to the local Ollama API and parse the reply. Never raises."""
    with Session(engine) as session:
        t = session.get(AITask, task_id)
        if t is None:
            return
        cfg = get_ai(session)
        t.status, t.error_message, t.updated_at = "running", "", utcnow()
        session.commit()
        prompt, model, timeout = t.prompt, cfg.ollama_model, cfg.ollama_timeout_s
    try:
        reply = ollama.generate(prompt, model, timeout)
    except ollama.OllamaError as e:
        with Session(engine) as session:
            t = session.get(AITask, task_id)
            t.status, t.error_message, t.updated_at = "failed", str(e), utcnow()
            session.commit()
        return
    with Session(engine) as session:
        submit_reply(session, session.get(AITask, task_id), reply, provider="ollama")


def run_ollama_in_background(engine, task_id: int) -> None:
    threading.Thread(target=run_ollama, args=(engine, task_id), name=f"ollama-{task_id}", daemon=True).start()
