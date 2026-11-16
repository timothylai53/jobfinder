"""Ollama provider against a MOCKED local API (Ollama isn't installed). Not running, model missing, timeout,
a good reply, and the ollama_deep_analysis automation (default OFF)."""
import json
import time
from pathlib import Path

import httpx
import pytest
from sqlmodel import Session, select

from ai import ollama
from models import AITask, AutomationRun, Document, MatchResult
from scheduler.automations import run_automation

FIX = Path(__file__).parent / "fixtures" / "ai"


def fx(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _content(reply_file: str) -> str:
    """Ollama with format=json returns bare JSON; take it from the fixture's code block."""
    from ai.parser import extract_json_text
    return extract_json_text(fx(reply_file))


@pytest.fixture
def fake_ollama():
    """A fake local Ollama: models installed, chat replies by task, and the requests it received."""
    state = {"models": ["qwen2.5:3b"], "replies": {}, "seen": [], "down": False, "slow": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if state["down"]:
            raise httpx.ConnectError("connection refused", request=request)
        state["seen"].append(request)
        assert request.url.host == "127.0.0.1" and request.url.port == 11434  # only ever the local API
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in state["models"]]})
        if request.url.path == "/api/chat":
            if state["slow"]:
                raise httpx.ReadTimeout("timed out", request=request)
            body = json.loads(request.content)
            if body["model"] not in state["models"]:
                return httpx.Response(404, json={"error": f"model '{body['model']}' not found"})
            prompt = body["messages"][0]["content"]
            task = next((k for k in state["replies"] if k in prompt), None)
            return httpx.Response(200, json={"message": {"role": "assistant",
                                                          "content": state["replies"].get(task, "{}")}})
        return httpx.Response(404)

    ollama.set_transport_factory(lambda: httpx.MockTransport(handler))
    yield state
    ollama.set_transport_factory(None)


def test_status_messages(fake_ollama):
    st = ollama.status("qwen2.5:3b")
    assert st["running"] and st["installed"] and st["message"] == "Ready."
    st = ollama.status("llama3.2:3b")
    assert st["running"] and not st["installed"] and "ollama pull llama3.2:3b" in st["message"]
    fake_ollama["down"] = True
    st = ollama.status("qwen2.5:3b")
    assert not st["running"] and "Ollama is not running" in st["message"]


def test_latest_tag_counts_as_installed(fake_ollama):
    fake_ollama["models"] = ["llama3.2:latest"]
    assert ollama.status("llama3.2")["installed"]


@pytest.mark.parametrize("setup,kind,message", [
    (lambda s: s.update(down=True), "not_running", "Ollama is not running"),
    (lambda s: s.update(models=[]), "model_missing", "ollama pull qwen2.5:3b"),
    (lambda s: s.update(slow=True), "timeout", "longer than 60 s"),
])
def test_generate_errors_are_clear(fake_ollama, setup, kind, message):
    setup(fake_ollama)
    with pytest.raises(ollama.OllamaError) as e:
        ollama.generate("hi", "qwen2.5:3b", 60)
    assert e.value.kind == kind and message in str(e.value)


# ---------- through the API: the same flow, automatically ----------

def _bank_and_job(client):
    from tests.test_ai_flow import BANK, JD
    client.post("/api/resumes/import", json={"name": "Fake", "items": BANK, "profile": {"name": "Ali Bin Contoh"}})
    return client.post("/api/jobs/manual", json={"title": "Junior Software Engineer", "company": "Syarikat Contoh Bhd",
                                                 "description": JD}).json()["id"]


def _wait(client, task_id: int) -> dict:
    for _ in range(200):
        t = client.get(f"/api/ai/tasks/{task_id}").json()
        if t["status"] != "running":
            return t
        time.sleep(0.02)
    raise AssertionError("Ollama task never finished")


def test_tailor_resume_via_ollama_then_same_review(client, fake_ollama):
    job_id = _bank_and_job(client)
    fake_ollama["replies"]["tailor their resume"] = _content("tailor_fabricated.txt")
    t = client.post("/api/ai/tasks", json={"task": "tailor_resume", "job_id": job_id, "provider": "ollama"}).json()
    assert t["provider"] == "ollama" and t["status"] == "running"
    t = _wait(client, t["id"])
    assert t["status"] == "parsed" and any(f["kind"] == "unknown_id" for f in t["flags"])  # same guard
    chat = next(r for r in fake_ollama["seen"] if r.url.path == "/api/chat")
    body = json.loads(chat.content)
    assert body["stream"] is False and body["format"] == "json" and "[B1]" in body["messages"][0]["content"]


def test_ollama_not_running_shows_a_clear_message_and_can_retry(client, fake_ollama):
    job_id = _bank_and_job(client)
    fake_ollama["down"] = True
    t = client.post("/api/ai/tasks", json={"task": "cover_letter", "job_id": job_id, "provider": "ollama"}).json()
    t = _wait(client, t["id"])
    assert t["status"] == "failed" and "Ollama is not running" in t["error_message"]
    assert "Never invent" in t["prompt"]  # the prompt is there: Copy-Paste still works for this task
    fake_ollama["down"] = False
    fake_ollama["replies"]["cover letter"] = _content("cover_letter_valid.txt")
    client.post(f"/api/ai/tasks/{t['id']}/run-ollama")
    done = _wait(client, t["id"])
    assert done["status"] == "parsed" and done["provider"] == "ollama"


def test_pasting_a_reply_after_ollama_failed_counts_as_copy_paste(client, fake_ollama):
    job_id = _bank_and_job(client)
    fake_ollama["down"] = True
    t = _wait(client, client.post("/api/ai/tasks", json={"task": "deep_analysis", "job_id": job_id, "provider": "ollama"}).json()["id"])
    assert t["status"] == "failed"
    t = client.post(f"/api/ai/tasks/{t['id']}/reply", json={"reply": fx("deep_analysis_valid.txt")}).json()
    assert t["provider"] == "copy_paste"
    doc = client.post("/api/documents/from-task", json={"ai_task_id": t["id"]}).json()
    assert doc["source"] == "copy_paste"


def test_ollama_status_endpoint(client, fake_ollama):
    st = client.get("/api/ai/ollama/status").json()
    assert st["running"] and st["model"] == "qwen2.5:3b" and st["installed"]


# ---------- the ollama_deep_analysis automation ----------

def _automation(client, enabled=True):
    from app.db import engine
    from models import Automation
    with Session(engine) as s:
        s.get(Automation, "ollama_deep_analysis").enabled = enabled
        s.commit()
    return engine


def test_automation_analyses_high_matches_once(client, fake_ollama):
    job_id = _bank_and_job(client)
    low = client.post("/api/jobs/manual", json={"title": "Draughtman", "description": "Prepare drawings."}).json()["id"]
    fake_ollama["replies"]["honest and specific"] = _content("deep_analysis_valid.txt")
    settings = client.get("/api/settings").json()
    settings["general"]["high_match_threshold"] = 30
    client.put("/api/settings", json=settings)
    engine = _automation(client)
    run_id = run_automation(engine, "ollama_deep_analysis", "manual")
    with Session(engine) as s:
        run = s.get(AutomationRun, run_id)
        assert run.result == "ok" and run.items_processed == 1 and "1 job(s) analysed with qwen2.5:3b" in run.message
        docs = s.exec(select(Document).where(Document.type == "deep_analysis")).all()
        assert [d.job_id for d in docs] == [job_id] and docs[0].source == "ollama"  # the low-confidence job is skipped
        assert s.exec(select(MatchResult).where(MatchResult.method == "deep")).one().job_id == job_id
        assert low not in [d.job_id for d in docs]
    run_id = run_automation(engine, "ollama_deep_analysis", "manual")  # nothing new the second time
    with Session(engine) as s:
        assert s.get(AutomationRun, run_id).items_processed == 0
        assert len(s.exec(select(AITask).where(AITask.provider == "ollama")).all()) == 1


def test_automation_reports_ollama_not_running(client, fake_ollama):
    _bank_and_job(client)
    fake_ollama["down"] = True
    engine = _automation(client)
    run_id = run_automation(engine, "ollama_deep_analysis", "manual")
    with Session(engine) as s:
        run = s.get(AutomationRun, run_id)
        assert run.result == "error" and "Ollama is not running" in run.message


def test_automation_skips_when_ai_is_off(client, fake_ollama):
    client.put("/api/ai/settings", json={**client.get("/api/ai/settings").json(), "mode": "off"})
    engine = _automation(client)
    run_id = run_automation(engine, "ollama_deep_analysis", "manual")
    with Session(engine) as s:
        run = s.get(AutomationRun, run_id)
        assert run.result == "ok" and "AI is switched off" in run.message
    assert fake_ollama["seen"] == []
