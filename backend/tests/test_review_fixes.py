"""Regression tests for bugs found by the code review and the type checker (DECISIONS.md, Task 2)."""
from datetime import UTC, datetime

from sqlmodel import Session, select


def test_ollama_run_survives_a_task_deleted_meanwhile(client, monkeypatch):
    """The AI task (or its job) is deleted while Ollama is still working: the background run just stops."""
    from ai import ollama, service
    from app.db import engine
    from models import AITask

    with Session(engine) as s:
        t = AITask(task="deep_analysis", provider="ollama", prompt="p")
        s.add(t)
        s.commit()
        tid = t.id

    def deleted_meanwhile(*a, **k):
        with Session(engine) as s:
            s.delete(s.get(AITask, tid))
            s.commit()
        return '{"requirements": [], "overall_fit": 50}'

    monkeypatch.setattr(ollama, "generate", deleted_meanwhile)
    service.run_ollama(engine, tid)  # used to raise AttributeError on None

    def fails(*a, **k):
        with Session(engine) as s:
            obj = s.get(AITask, tid)
            if obj:
                s.delete(obj)
                s.commit()
        raise ollama.OllamaError("not_running", "Ollama is not running")

    with Session(engine) as s:
        s.add(AITask(id=tid, task="deep_analysis", provider="ollama", prompt="p"))
        s.commit()
    monkeypatch.setattr(ollama, "generate", fails)
    service.run_ollama(engine, tid)


def test_paused_source_without_an_end_time_does_not_crash(client):
    from app.db import engine
    from models import Source
    from sources import health
    with Session(engine) as s:
        src = s.get(Source, "indeed")
        src.status, src.paused_until = "paused", None
        ok, why = health.can_run(src, datetime(2026, 11, 20, tzinfo=UTC))
        assert ok is False and why == "paused (no end time set)"


# ---------- independent code review (R-numbers as in DECISIONS.md #178) ----------

def _job(client, title, company="Kedai Contoh", location="Kuala Lumpur", jd="Requirements:\n- Python\n- SQL"):
    return client.post("/api/jobs/manual", json={"title": title, "company": company, "location": location,
                                                 "description": jd}).json()["id"]


def test_r1_merging_duplicates_never_deletes_documents_or_a_second_tracker_entry(client):
    from app.db import engine
    from models import Document, Job
    from scheduler.automations import merge_duplicates
    a, b = _job(client, "Junior Dev"), _job(client, "Graduate Dev")
    with Session(engine) as s:  # make b a duplicate of a after the fact (as a location tidy could)
        ja, jb = s.get(Job, a), s.get(Job, b)
        jb.title, jb.dedupe_key = ja.title, ja.dedupe_key
        s.add(Document(job_id=b, type="resume", version=1, content={}, source="manual"))
        s.commit()
        assert merge_duplicates(s) == 0  # b has a resume version: kept, not merged away
        assert s.get(Job, b) is not None and len(s.exec(select(Document).where(Document.job_id == b)).all()) == 1
    for jid in (a, b):
        client.post("/api/applications", json={"job_id": jid})
    with Session(engine) as s:
        for d in s.exec(select(Document).where(Document.job_id == b)).all():
            s.delete(d)
        s.commit()
        assert merge_duplicates(s) == 0  # both tracked: neither tracker entry is dropped


def test_r1_a_plain_duplicate_is_still_merged_and_keeps_its_tracker_entry(client):
    from app.db import engine
    from models import Application, Job
    from scheduler.automations import merge_duplicates
    a, b = _job(client, "Junior Dev"), _job(client, "Graduate Dev")
    client.post("/api/applications", json={"job_id": b})
    with Session(engine) as s:
        ja, jb = s.get(Job, a), s.get(Job, b)
        jb.title, jb.dedupe_key = ja.title, ja.dedupe_key
        s.commit()
        assert merge_duplicates(s) == 1
        assert s.get(Job, b) is None and s.exec(select(Application)).one().job_id == a


def test_r3_stored_cards_do_not_use_up_the_cap():
    from types import SimpleNamespace

    from sources.jobstreet import JobStreetSource
    cards = [{"id": str(i), "title": f"Dev {i}", "work_type": "", "listed": ""} for i in range(1, 31)]
    src = JobStreetSource(client=SimpleNamespace(), max_results=5, known_ids={str(i) for i in range(1, 6)})
    src.search = lambda *a, **k: cards
    src.parse_card = staticmethod(lambda c: c)
    asked = []
    src.detail = lambda job_id: asked.append(job_id) or None
    src.to_normalized = lambda card, full: card["id"]
    profile = SimpleNamespace(keywords=["dev"], locations=["Kuala Lumpur"], days=0, job_type="", max_results=0)
    assert src.fetch(profile) == ["6", "7", "8", "9", "10"]  # the 5 stored cards are skipped, not counted
    assert asked == ["6", "7", "8", "9", "10"]


def test_r6_a_late_ollama_reply_does_not_replace_a_pasted_one(client, monkeypatch):
    from ai import ollama, service
    from app.db import engine
    from models import AITask
    with Session(engine) as s:
        t = AITask(task="deep_analysis", provider="ollama", prompt="p")
        s.add(t)
        s.commit()
        tid = t.id

    def user_pastes_meanwhile(*a, **k):
        with Session(engine) as s:
            t = s.get(AITask, tid)
            t.provider, t.status, t.response = "copy_paste", "parsed", "pasted by the user"
            s.commit()
        return "late ollama reply"

    monkeypatch.setattr(ollama, "generate", user_pastes_meanwhile)
    service.run_ollama(engine, tid)
    with Session(engine) as s:
        t = s.get(AITask, tid)
        assert (t.provider, t.status, t.response) == ("copy_paste", "parsed", "pasted by the user")


def test_r8_daily_run_counter_rolls_over_at_local_midnight(client):
    from datetime import timedelta

    from app.db import engine
    from models import Source
    from sources import health
    with Session(engine) as s:
        src = s.get(Source, "indeed")
        local_midnight = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        health.record_run(src, local_midnight - timedelta(minutes=30))  # yesterday evening, local time
        health.record_run(src, local_midnight + timedelta(minutes=30))  # just after midnight
        assert src.runs_today == 1 and src.runs_date == local_midnight.date()


def test_r9_today_lists_no_rough_high_matches(client):
    from sources.ingest import SUMMARY_ONLY
    good = _job(client, "Junior Dev")
    rough = _job(client, "Teaser Dev", company="Contoh Two", jd=f"{SUMMARY_ONLY}\nRequirements:\n- Python\n- SQL")
    ids = {j["id"] for j in client.get("/api/dashboard").json()["high_match_jobs"]}
    assert rough not in ids and (good in ids or not ids)


def test_r10_a_malformed_url_is_a_readable_error(client):
    r = client.post("/api/jobs/fetch-url", json={"url": "https://example.com:99999/job"})
    assert r.status_code == 200 and r.json()["ok"] is False and "valid web address" in r.json()["error"]


def test_r13_undo_of_hide_lets_filter_rules_decide_again(client):
    from app.db import engine
    from models import Job
    jid = _job(client, "Junior Dev")
    client.patch(f"/api/jobs/{jid}", json={"hidden": True})
    client.patch(f"/api/jobs/{jid}", json={"restore": True})
    with Session(engine) as s:
        j = s.get(Job, jid)
        assert (j.hidden, j.hidden_by) == (False, "")
    client.patch(f"/api/jobs/{jid}", json={"hidden": False})  # a deliberate Unhide stays final
    with Session(engine) as s:
        assert s.get(Job, jid).hidden_by == "manual"


def test_r14_url_import_respects_jobstreet_switched_off(client):
    assert client.put("/api/sources/jobstreet", json={"enabled": False, "max_results": 5, "max_runs_per_day": 1}).status_code == 200
    r = client.post("/api/jobs/fetch-url", json={"url": "https://my.jobstreet.com/job/95667394"}).json()
    assert r["ok"] is False and "switched off" in r["error"]


def test_r16_deleting_a_deep_analysis_removes_its_deep_score(client):
    from app.db import engine
    from documents.service import save_analysis
    from models import MatchResult
    jid = _job(client, "Junior Dev")
    with Session(engine) as s:
        doc = save_analysis(s, jid, "deep_analysis", {"requirements": [], "overall_fit": 70}, "manual", None)
    assert client.delete(f"/api/documents/{doc.id}").status_code == 200
    with Session(engine) as s:
        assert s.exec(select(MatchResult).where(MatchResult.method == "deep")).all() == []


def test_r17_document_source_is_validated(client):
    jid = _job(client, "Junior Dev")
    r = client.post("/api/documents/cover-letter", json={"job_id": jid, "source": "whatever", "greeting": "Hi",
                                                         "paragraphs": ["x"], "closing": "Bye"})
    assert r.status_code == 422
