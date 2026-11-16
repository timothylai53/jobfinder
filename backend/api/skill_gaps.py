"""Skill gaps: what to learn next. Missing required/preferred skills across jobs, ranked by how often asked."""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from models import Application, Job, MatchResult

router = APIRouter(prefix="/api/skill-gaps", tags=["skill-gaps"])


def aggregate(jobs: list[Job], matches: dict[int, MatchResult]) -> tuple[list[dict], list[dict]]:
    gaps: dict[str, dict] = {}
    soft: dict[str, dict] = {}

    def add(table: dict, name: str, kind: str, job: Job, score: int) -> None:
        row = table.setdefault(name, {"skill": name, "required": 0, "preferred": 0, "jobs": []})
        row[kind] += 1
        if not any(j["id"] == job.id for j in row["jobs"]):
            row["jobs"].append({"id": job.id, "title": job.title, "company": job.company, "score": score, "kind": kind})

    for job in jobs:
        m = matches.get(job.id)
        if not m:
            continue
        for cat in m.breakdown.get("categories", []):
            kind = {"required_skills": "required", "preferred_skills": "preferred"}.get(cat["key"])
            if not kind:
                continue
            for item in cat.get("items", []):
                if item.get("status") == "not_met":
                    add(gaps, item["name"], kind, job, m.total)
        for s in m.breakdown.get("soft_skills", []) or []:
            if s.get("status") == "not_met":
                add(soft, s["name"], "required" if s.get("kind") == "required" else "preferred", job, m.total)

    def ranked(table: dict) -> list[dict]:
        rows = list(table.values())
        for r in rows:
            r["total"] = r["required"] + r["preferred"]
            r["jobs"].sort(key=lambda j: -j["score"])
        return sorted(rows, key=lambda r: (-r["required"], -r["total"], r["skill"].lower()))

    return ranked(gaps), ranked(soft)


@router.get("")
def skill_gaps(scope: str = "saved", min_score: int = 60, session: Session = Depends(get_session)):
    """scope=saved: jobs in my tracker (not Rejected/Withdrawn). scope=scored: every visible job scoring >= min_score."""
    matches = {m.job_id: m for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    if scope == "scored":
        jobs = [j for j in session.exec(select(Job).where(Job.hidden == False)).all()  # noqa: E712
                if j.id in matches and matches[j.id].total >= min_score]
    else:
        active = {a.job_id for a in session.exec(select(Application)).all() if a.status not in ("Rejected", "Withdrawn")}
        jobs = [j for j in session.exec(select(Job)).all() if j.id in active]
    gaps, soft = aggregate(jobs, matches)
    return {"scope": scope, "min_score": min_score, "jobs_considered": len(jobs), "gaps": gaps, "soft_skills": soft}
