"""Shared pipeline for every source: normalize -> dedupe -> save JD snapshot -> filter -> quick score.

Used unchanged by manual import, URL import and every fetched source.
"""
from sqlmodel import Session, select

from filters.service import apply_to_job, load_rules
from matcher.service import Scorer
from models import Job
from sources.base import NormalizedJob, dedupe_key, locations_compatible, tidy_location

SUMMARY_ONLY = "(Summary only: the full job description could not be fetched.)"


def tidy_stored_locations(session: Session) -> int:
    """Existing jobs saved before locations were tidied (e.g. Indeed's "Kuala Lumpur, M14, Malaysia")."""
    changed = 0
    for job in session.exec(select(Job)).all():
        tidy = tidy_location(job.location)
        if tidy != job.location:
            job.location, job.dedupe_key = tidy, dedupe_key(job.company, job.title, tidy)
            changed += 1
    session.commit()
    return changed


def low_confidence(mr) -> str:
    """Why a quick score can't be trusted (e.g. no recognised skills in the JD), or ""."""
    return (mr.breakdown or {}).get("low_confidence", "") if mr is not None else ""


def is_summary_only(job: Job) -> bool:
    """Saved from a search card only: its score is rough until the full JD is pasted."""
    return SUMMARY_ONLY in (job.description or "")


def _find_existing(session: Session, nj: NormalizedJob, key: str) -> Job | None:
    ext = nj.extra.get("external_ids") or {}
    if ext:  # same job on the same site, even if title/company changed slightly
        for job in session.exec(select(Job)).all():
            if any(job.external_ids.get(site) == jid for site, jid in ext.items()):
                return job
    exact = session.exec(select(Job).where(Job.dedupe_key == key)).first()
    if exact:
        return exact
    # Same company + title, location written differently by another site
    base = key.rsplit("|", 1)[0] + "|"
    for job in session.exec(select(Job).where(Job.dedupe_key.startswith(base))).all():
        if locations_compatible(job.location, nj.location):
            return job
    return None


def _better_description(new: str, old: str) -> bool:
    if not new.strip():
        return False
    if SUMMARY_ONLY in old and SUMMARY_ONLY not in new:
        return True
    if SUMMARY_ONLY in new and SUMMARY_ONLY not in old:
        return False
    return len(new) > len(old)


def ingest(session: Session, items: list[NormalizedJob], scorer: Scorer | None = None) -> list[tuple[Job, bool]]:
    """Save jobs; returns (job, is_duplicate) per input. Duplicates are merged, never re-created."""
    rules = load_rules(session)
    scorer = scorer or Scorer(session)
    out: list[tuple[Job, bool]] = []
    for nj in items:
        nj.location = tidy_location(nj.location)
        key = dedupe_key(nj.company, nj.title, nj.location)
        job = _find_existing(session, nj, key)
        dup = job is not None
        ext = nj.extra.get("external_ids") or {}
        if job is None:
            job = Job(
                title=nj.title.strip(), company=nj.company.strip(), location=nj.location.strip(),
                description=nj.description.strip(), salary_min=nj.salary_min, salary_max=nj.salary_max,
                salary_currency=nj.salary_currency, job_type=nj.job_type, work_arrangement=nj.work_arrangement,
                posted_date=nj.posted_date,
                urls=[nj.url] if nj.url else [], sources=[nj.source], dedupe_key=key, external_ids=dict(ext),
            )
            session.add(job)
        else:
            if nj.url and nj.url not in job.urls:
                job.urls = [*job.urls, nj.url]
            if nj.source not in job.sources:
                job.sources = [*job.sources, nj.source]
            if ext and any(job.external_ids.get(k) != v for k, v in ext.items()):
                job.external_ids = {**job.external_ids, **ext}
            if _better_description(nj.description, job.description):
                job.description = nj.description.strip()
            for f in ("salary_min", "salary_max", "salary_currency", "job_type", "work_arrangement", "posted_date"):
                if not getattr(job, f) and getattr(nj, f):
                    setattr(job, f, getattr(nj, f))
        session.flush()
        apply_to_job(job, rules)
        scorer.score(job)
        out.append((job, dup))
    session.commit()
    for job, _ in out:
        session.refresh(job)
    return out
