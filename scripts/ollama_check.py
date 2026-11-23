"""Run real AI tasks through the local Ollama provider on the FAKE demo data, and report speed, whether each reply
parsed (and which repairs it needed), what the fabrication guard flagged (red / amber), and how often a tailored
bullet reused a number from its bank item for a different claim ("team of 3" from "3 operations teams"), which the
guard can't see.

    backend\\.venv\\Scripts\\python scripts\\ollama_check.py [model] [jobs] [rounds] [label]   (qwen2.5:3b 3 1 run)

Needs Ollama running on 127.0.0.1:11434 with the model pulled. Reseeds demo_data/ first so runs are comparable;
never touches data/. Nothing leaves the laptop: Ollama is local.
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seed_demo import ROOT, demo_env, safe_target, seed  # noqa: E402

TASKS = ("deep_analysis", "tailor_resume", "cover_letter")
AMBER = {"skill_not_in_item", "header_removed", "several_bullets"}  # the guard's "worth a look" kinds; the rest are red
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
SMALL = {"a", "an", "the", "of", "by", "in", "to", "for", "with", "and", "or", "on", "at", "from", "over", "than", "about"}


def _neighbours(text: str, number: str) -> list[set[str]]:
    """For each place `number` appears: the nearest real word before and after it (first 4 letters, small words
    skipped), so "a team of 4" and "Led a team of 4 using" both give {"team", ...}."""
    words = re.findall(r"[A-Za-z]+|\d+(?:[.,]\d+)?", text)
    out = []
    for i, w in enumerate(words):
        if w != number:
            continue
        near = set()
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(words) and (words[j].lower() in SMALL or words[j][0].isdigit()):
                j += step
            if 0 <= j < len(words):
                near.add(words[j].lower()[:4])
        out.append(near)
    return out


def reused_numbers(result: dict, bank: dict[str, str]) -> list[str]:
    """Bullets that use a number found in their own bank item but next to different words, e.g. "led a team of 3"
    from "used by 3 operations teams". The guard can't see these; this is only a measurement, not a check."""
    out = []
    for sec in result.get("sections", []):
        for it in sec.get("items", []):
            source = bank.get(str(it.get("source_id", "")).strip().upper())
            text = it.get("text", "")
            if not source:
                continue
            for num in dict.fromkeys(NUMBER.findall(text)):
                theirs = _neighbours(source, num)
                if not theirs:
                    continue  # not in the item at all: the guard's new_number flag covers that
                mine = set().union(*_neighbours(text, num))
                if not any(mine & t for t in theirs):
                    out.append(f"{it.get('source_id')}: {text[:90]}")
                    break
    return out


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"
    n_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    label = sys.argv[4] if len(sys.argv) > 4 else "run"
    target = safe_target(None)
    seed(target)  # the same starting data for every run, so before/after comparisons are fair
    os.environ.update({**demo_env(target), "JOBFINDER_NO_AUTO_BACKUP": "1"})
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlmodel import Session, select

    from ai import service
    from app.db import engine
    from app.main import init_db
    from app.settings_store import get_ai, set_ai
    from models import AITask, ExperienceItem, Job

    init_db()
    with Session(engine) as s:
        cfg = get_ai(s)
        cfg.mode, cfg.ollama_model = "ollama", model
        set_ai(s, cfg)
        jobs = [j for j in s.exec(select(Job).where(Job.hidden == False)).all()][:n_jobs]  # noqa: E712
        job_ids = [(j.id, j.title) for j in jobs]
        bank = {i.code.upper(): "\n".join([i.title, i.organization, i.start, i.end, *i.bullets])
                for i in s.exec(select(ExperienceItem)).all()}

    results = []
    for r in range(rounds):
        for job_id, title in job_ids:
            for task in TASKS:
                with Session(engine) as s:
                    tid = service.create(s, task, job_id, provider="ollama").id
                start = time.perf_counter()
                service.run_ollama(engine, tid)
                secs = time.perf_counter() - start
                with Session(engine) as s:
                    t = s.get(AITask, tid)
                    kinds = Counter(f["kind"] for f in t.flags or [])
                    reused = reused_numbers(t.result or {}, bank) if task == "tailor_resume" else []
                    row = {"round": r + 1, "job": title, "task": task, "seconds": round(secs, 1), "status": t.status,
                           "error": t.error_message, "repairs": t.repairs, "errors": [e.get("path") for e in t.errors or []],
                           "flags": kinds, "red": sum(n for k, n in kinds.items() if k not in AMBER),
                           "amber": sum(n for k, n in kinds.items() if k in AMBER), "reused_numbers": reused,
                           "flag_msgs": [f["message"] for f in (t.flags or [])][:8], "response": t.response}
                results.append(row)
                print(f"{task:14} {title[:30]:30} {row['seconds']:6.1f}s {row['status']:8} red={row['red']} "
                      f"amber={row['amber']} reused={len(reused)} flags={dict(kinds)}", flush=True)

    out = ROOT / "demo_data" / f"ollama-check-{model.replace(':', '_')}-{label}.json"
    out.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(f"\n== {label}: {len(results)} replies")
    for task in TASKS:
        rows = [x for x in results if x["task"] == task]
        if rows:
            print(f"{task:14} parsed {sum(x['status'] == 'parsed' for x in rows)}/{len(rows)}  "
                  f"red {sum(x['red'] for x in rows)}  amber {sum(x['amber'] for x in rows)}  "
                  f"reused-number claims {sum(len(x['reused_numbers']) for x in rows)}  "
                  f"median {sorted(x['seconds'] for x in rows)[len(rows) // 2]} s")
    print(f"details in {out}")


if __name__ == "__main__":
    main()
