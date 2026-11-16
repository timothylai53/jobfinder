"""The automations (brief §6.10). Each one: on/off, manual or scheduled, "Run now", every run logged.

Automations use rule-based logic only (never Copy-Paste AI). `ollama_deep_analysis` comes in Phase 3.
"""
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from app.settings_store import get_ai, get_general
from filters.service import reapply_all
from matcher.service import Scorer
from models import Application, Automation, AutomationRun, Document, Job, MatchResult
from models._base import utcnow
from notifications.service import notify
from sources.base import locations_compatible
from sources.ingest import is_summary_only, low_confidence
from sources.runner import run_fetch


@dataclass
class Spec:
    label: str
    description: str
    enabled: bool
    schedule: str  # "HH:MM" daily, or "after:fetch_jobs"


SPECS: dict[str, Spec] = {
    "fetch_jobs": Spec("Fetch jobs", "Run every enabled source for each enabled search profile.", False, "09:00"),
    "dedupe_and_filter": Spec("Dedupe and filter", "Merge duplicate jobs and re-apply filter rules.", True, "after:fetch_jobs"),
    "score_new_jobs": Spec("Score new jobs", "Quick-score jobs that have no score yet.", True, "after:fetch_jobs"),
    "high_match_alert": Spec("High-match alert", "Notify me about new jobs scoring at or above the threshold.", True,
                             "after:fetch_jobs"),
    "follow_up_reminder": Spec("Follow-up reminder", "Notify me when an Applied job passes its follow-up date.", True, "09:00"),
    "ollama_deep_analysis": Spec("Deep analysis with Ollama",
                                 "Run deep analysis through local Ollama on new jobs at or above the high-match "
                                 "threshold. Never uses Copy-Paste.", False, "after:fetch_jobs"),
}
AFTER_FETCH = ["dedupe_and_filter", "score_new_jobs", "high_match_alert", "ollama_deep_analysis"]


def seed(session: Session) -> None:
    for key, spec in SPECS.items():
        if session.get(Automation, key) is None:
            session.add(Automation(key=key, enabled=spec.enabled, mode="scheduled", schedule=spec.schedule))
    session.commit()


# ---------- the tasks: (session, **options) -> (items processed, message) ----------

def task_fetch_jobs(session: Session, **opts) -> tuple[int, str, bool]:
    results = run_fetch(session, source_keys=opts.get("source_keys"), profile_ids=opts.get("profile_ids"),
                        results_cap=opts.get("results_cap"))
    lines = [f"{r.label()}: {r.status}: {r.message} ({r.requests} request(s))" for r in results]
    ran = [r for r in results if r.status != "skipped"]
    failed = bool(ran) and all(r.status in ("error", "paused") for r in ran)
    return sum(r.new for r in results), "\n".join(lines) or "no sources", failed


def merge_duplicates(session: Session) -> int:
    """Jobs with the same company + title and compatible locations become one (oldest kept)."""
    jobs = session.exec(select(Job).order_by(Job.id)).all()
    removed = 0
    keep_by_base: dict[str, list[Job]] = {}
    for job in jobs:
        base = job.dedupe_key.rsplit("|", 1)[0]
        target = next((k for k in keep_by_base.get(base, []) if locations_compatible(k.location, job.location)), None)
        if target is None:
            keep_by_base.setdefault(base, []).append(job)
            continue
        target.urls = list(dict.fromkeys([*target.urls, *job.urls]))
        target.sources = list(dict.fromkeys([*target.sources, *job.sources]))
        target.external_ids = {**job.external_ids, **target.external_ids}
        if len(job.description) > len(target.description) and "Summary only" not in job.description:
            target.description = job.description
        app = session.exec(select(Application).where(Application.job_id == job.id)).first()
        if app and not session.exec(select(Application).where(Application.job_id == target.id)).first():
            app.job_id = target.id  # keep my tracker entry
        session.delete(job)  # its MatchResult goes with it (ON DELETE CASCADE)
        removed += 1
    session.commit()
    return removed


def task_dedupe_and_filter(session: Session, **_) -> tuple[int, str, bool]:
    merged = merge_duplicates(session)
    hidden = reapply_all(session)
    return merged, f"{merged} duplicate(s) merged; {hidden} job(s) hidden by filter rules", False


def task_score_new_jobs(session: Session, **_) -> tuple[int, str, bool]:
    scored_ids = set(session.exec(select(MatchResult.job_id).where(MatchResult.method == "quick")).all())
    todo = [j for j in session.exec(select(Job)).all() if j.id not in scored_ids]
    if todo:
        scorer = Scorer(session)
        for j in todo:
            scorer.score(j)
        session.commit()
    return len(todo), f"{len(todo)} job(s) scored", False


def task_high_match_alert(session: Session, **_) -> tuple[int, str, bool]:
    threshold = get_general(session).high_match_threshold
    tracked = set(session.exec(select(Application.job_id)).all())
    results = session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()
    scores = {m.job_id: m.total for m in results if not low_confidence(m)}  # rough scores never alert
    # Summary-only jobs have a rough score: not alerted (and not marked), so pasting the full JD can still alert later
    hits = [j for j in session.exec(select(Job).where(Job.hidden == False, Job.high_match_notified == False)).all()  # noqa: E712
            if scores.get(j.id, 0) >= threshold and j.id not in tracked and not is_summary_only(j)]
    hits.sort(key=lambda j: -scores[j.id])
    for j in hits[:10]:
        notify(session, "high_match", f"High match ({scores[j.id]}): {j.title}" + (f" at {j.company}" if j.company else ""),
               f"/jobs/{j.id}")
    if len(hits) > 10:
        notify(session, "high_match", f"…and {len(hits) - 10} more high-match jobs", "/jobs")
    for j in hits:
        j.high_match_notified = True
    session.commit()
    return len(hits), f"{len(hits)} new job(s) at or above {threshold}", False


def task_follow_up_reminder(session: Session, today: date | None = None, **_) -> tuple[int, str, bool]:
    today = today or date.today()
    jobs = {j.id: j for j in session.exec(select(Job)).all()}
    due = [a for a in session.exec(select(Application).where(Application.status == "Applied")).all()
           if a.follow_up_at and a.follow_up_at <= today and a.reminded_on != a.follow_up_at]
    for a in due:
        j = jobs.get(a.job_id)
        notify(session, "follow_up", f"Follow up on your application: {j.title if j else 'a job'}"
               + (f" at {j.company}" if j and j.company else ""), f"/jobs/{a.job_id}")
        a.reminded_on = a.follow_up_at  # this follow-up date has been reminded; a new date reminds again
    session.commit()
    return len(due), f"{len(due)} reminder(s)", False


def task_ollama_deep_analysis(session: Session, **_) -> tuple[int, str, bool]:
    """Deep analysis via the LOCAL Ollama API for new jobs at or above the high-match threshold (brief §6.10).
    Skips summary-only and low-confidence jobs and jobs that already have an analysis. Saved automatically
    (an analysis isn't resume content); the fabrication guard's flags are kept with it."""
    from ai import ollama
    from ai import service as ai_service
    from documents.service import save_analysis

    cfg = get_ai(session)
    if cfg.mode == "off":
        return 0, "skipped: AI is switched off in Settings", False
    st = ollama.status(cfg.ollama_model)
    if not st["running"] or not st["installed"]:
        return 0, st["message"], True
    threshold = get_general(session).high_match_threshold
    done = set(session.exec(select(Document.job_id).where(Document.type == "deep_analysis")).all())
    quick = {m.job_id: m for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    todo = [j for j in session.exec(select(Job).where(Job.hidden == False)).all()  # noqa: E712
            if j.id not in done and j.id in quick and quick[j.id].total >= threshold
            and not low_confidence(quick[j.id]) and not is_summary_only(j)]
    todo.sort(key=lambda j: -quick[j.id].total)
    todo = todo[:cfg.auto_analysis_max_per_run]
    analysed, problems = 0, []
    for job in todo:
        t = ai_service.create(session, "deep_analysis", job.id, provider="ollama")
        try:
            reply = ollama.generate(t.prompt, cfg.ollama_model, cfg.ollama_timeout_s)
        except ollama.OllamaError as e:
            t.status, t.error_message = "failed", str(e)
            session.commit()
            problems.append(f"{job.title}: {e}")
            if e.kind in ("not_running", "model_missing"):
                break
            continue
        t = ai_service.submit_reply(session, t, reply, provider="ollama")
        if t.status != "parsed":
            problems.append(f"{job.title}: the model's reply didn't match the format")
            continue
        save_analysis(session, job.id, "deep_analysis", t.result, "ollama", t.id, t.flags)
        analysed += 1
    msg = f"{analysed} job(s) analysed with {cfg.ollama_model}" if todo else "no new jobs at or above the threshold"
    if problems:
        msg += "; problems: " + "; ".join(problems)
    return analysed, msg, bool(problems) and analysed == 0


TASKS: dict[str, Callable[..., tuple[int, str, bool]]] = {
    "fetch_jobs": task_fetch_jobs, "dedupe_and_filter": task_dedupe_and_filter, "score_new_jobs": task_score_new_jobs,
    "high_match_alert": task_high_match_alert, "follow_up_reminder": task_follow_up_reminder,
    "ollama_deep_analysis": task_ollama_deep_analysis,
}

_locks = {k: threading.Lock() for k in SPECS}


def start_run(engine, key: str, trigger: str) -> int:
    """Create the log row up front (so an API can return its id before the work starts)."""
    with Session(engine) as session:
        run = AutomationRun(automation_key=key, trigger=trigger)
        session.add(run)
        session.commit()
        return run.id


def run_in_background(engine, key: str, trigger: str = "manual", **opts) -> int:
    run_id = start_run(engine, key, trigger)
    threading.Thread(target=run_automation, args=(engine, key, trigger), kwargs={"run_id": run_id, **opts},
                     name=f"automation-{key}", daemon=True).start()
    return run_id


def run_automation(engine, key: str, trigger: str = "manual", run_id: int | None = None, **opts) -> int:
    """Run one automation now and log it. Returns the AutomationRun id. Never raises."""
    run_id = run_id or start_run(engine, key, trigger)
    with Session(engine) as session:
        run = session.get(AutomationRun, run_id)
        if not _locks[key].acquire(blocking=False):
            run.result, run.message, run.finished_at = "skipped", "already running", utcnow()
            session.commit()
            return run_id
        try:
            items, message, failed = TASKS[key](session, **opts)
            run.result, run.items_processed, run.message = ("error" if failed else "ok"), items, message
        except Exception as e:  # noqa: BLE001 - a failing automation is logged, never crashes the app
            session.rollback()
            run = session.get(AutomationRun, run_id)
            run.result, run.error = "error", f"{e.__class__.__name__}: {e}"
        finally:
            _locks[key].release()
        run.finished_at = utcnow()
        auto = session.get(Automation, key)
        if auto is not None:
            auto.last_run_at = run.finished_at
        session.commit()
    if key == "fetch_jobs":
        with Session(engine) as session:
            chained = [k for k in AFTER_FETCH if (a := session.get(Automation, k)) and a.enabled and a.mode == "scheduled"]
        for k in chained:
            run_automation(engine, k, "chain")
    return run_id
