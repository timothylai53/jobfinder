"""Run real deep_analysis and tailor_resume tasks through the local Ollama provider on the FAKE demo data, and report
speed, whether the reply parsed (and which repairs it needed) and what the fabrication guard flagged.

    backend\\.venv\\Scripts\\python scripts\\ollama_check.py [model] [jobs] [rounds]     (defaults: qwen2.5:3b 3 1)

Needs Ollama running on 127.0.0.1:11434 with the model pulled. Uses demo_data/ (seeded if missing); never data/.
Nothing leaves the laptop: Ollama is local.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seed_demo import ROOT, demo_env, safe_target, seed  # noqa: E402


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"
    n_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    target = safe_target(None)
    if not (target / "jobfinder.db").exists():
        seed(target)
    os.environ.update({**demo_env(target), "JOBFINDER_NO_AUTO_BACKUP": "1"})
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlmodel import Session, select

    from ai import ollama, service
    from app.db import engine
    from app.main import init_db
    from app.settings_store import get_ai, set_ai
    from models import AITask, Job

    init_db()
    print("Ollama:", ollama.status(model) if hasattr(ollama, "status") else "", flush=True)
    with Session(engine) as s:
        cfg = get_ai(s)
        cfg.mode, cfg.ollama_model = "ollama", model
        set_ai(s, cfg)
        jobs = [j for j in s.exec(select(Job).where(Job.hidden == False)).all()][:n_jobs]  # noqa: E712
        job_ids = [(j.id, j.title) for j in jobs]

    results = []
    for r in range(rounds):
        for job_id, title in job_ids:
            for task in ("deep_analysis", "tailor_resume"):
                with Session(engine) as s:
                    t = service.create(s, task, job_id, provider="ollama")
                    tid = t.id
                start = time.perf_counter()
                service.run_ollama(engine, tid)
                secs = time.perf_counter() - start
                with Session(engine) as s:
                    t = s.get(AITask, tid)
                    row = {"round": r + 1, "job": title, "task": task, "seconds": round(secs, 1), "status": t.status,
                           "error": t.error_message, "repairs": t.repairs, "errors": [e.get("path") for e in t.errors or []],
                           "flags": Counter(f["kind"] for f in t.flags or []), "flag_msgs": [f["message"] for f in (t.flags or [])][:6],
                           "chars": len(t.response or "")}
                results.append(row)
                print(f"{task:14} {title[:34]:34} {row['seconds']:6.1f}s  {row['status']:8} repairs={row['repairs']} "
                      f"errors={row['errors'][:3]} flags={dict(row['flags'])}", flush=True)

    out = ROOT / "demo_data" / f"ollama-check-{model.replace(':', '_')}.json"
    out.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    parsed = sum(r["status"] == "parsed" for r in results)
    print(f"\n{parsed}/{len(results)} parsed; median {sorted(r['seconds'] for r in results)[len(results) // 2]} s; details in {out}")


if __name__ == "__main__":
    main()
