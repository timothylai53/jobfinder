import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from api import (
    ai,
    applications,
    automations,
    dashboard,
    documents,
    experience,
    export,
    filters,
    jobs,
    notifications,
    profile,
    resumes,
    settings,
    skill_gaps,
    skills,
    sources,
)
from app import security
from app.db import create_db, engine
from filters.service import seed_if_empty as seed_filters
from matcher.service import rescore_all
from scheduler import service as scheduler
from scheduler.automations import seed as seed_automations
from skills.service import remove_retired_aliases
from skills.service import seed_if_empty as seed_skills
from sources.health import seed as seed_sources
from sources.ingest import tidy_stored_locations

log = logging.getLogger("jobfinder")


def init_db() -> None:
    create_db()
    with Session(engine) as s:
        seed_skills(s)
        remove_retired_aliases(s)
        seed_filters(s)
        seed_sources(s)
        seed_automations(s)
        tidy_stored_locations(s)
        # Scores are stored; recompute them so a new version's rules apply to existing jobs.
        rescore_all(s)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler.start(engine)
    yield
    scheduler.stop()


app = FastAPI(title="JobFinder", lifespan=lifespan)
security.install(app)
for r in (profile, resumes, experience, skills, jobs, filters, applications, dashboard, export, settings, sources,
          automations, notifications, skill_gaps, ai, documents):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"ok": True}
