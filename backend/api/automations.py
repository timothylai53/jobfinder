from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import engine, get_session
from models import Automation, AutomationRun
from scheduler import service as scheduler
from scheduler.automations import SPECS, run_in_background

router = APIRouter(prefix="/api/automations", tags=["automations"])


def _out(a: Automation, last: AutomationRun | None) -> dict:
    spec = SPECS[a.key]
    return {**a.model_dump(), "label": spec.label, "description": spec.description,
            "default_enabled": spec.enabled, "daily": scheduler.is_daily(a.schedule),
            "last_run": last.model_dump() if last else None}


@router.get("")
def list_automations(session: Session = Depends(get_session)):
    out = []
    for key in SPECS:
        a = session.get(Automation, key)
        if a is None:
            continue
        last = session.exec(select(AutomationRun).where(AutomationRun.automation_key == key)
                            .order_by(AutomationRun.id.desc())).first()
        out.append(_out(a, last))
    return out


class AutomationUpdate(BaseModel):
    enabled: bool
    mode: str  # scheduled / manual
    schedule: str = ""


@router.put("/{key}")
def update_automation(key: str, data: AutomationUpdate, session: Session = Depends(get_session)):
    a = session.get(Automation, key)
    if not a:
        raise HTTPException(404, "Unknown automation")
    if data.mode not in ("scheduled", "manual"):
        raise HTTPException(422, "mode must be scheduled or manual")
    if scheduler.is_daily(a.schedule):  # daily ones: time can change; "after fetch" ones stay chained
        if not scheduler.is_daily(data.schedule):
            raise HTTPException(422, "Time must be HH:MM (24-hour), e.g. 09:00")
        a.schedule = data.schedule
    a.enabled, a.mode = data.enabled, data.mode
    session.commit()
    scheduler.reschedule()
    session.refresh(a)
    return _out(a, None)


@router.post("/{key}/run")
def run_now(key: str):
    if key not in SPECS:
        raise HTTPException(404, "Unknown automation")
    return {"run_id": run_in_background(engine, key, "manual")}


@router.get("/runs", response_model=list[AutomationRun])
def runs(limit: int = 50, session: Session = Depends(get_session)):
    return session.exec(select(AutomationRun).order_by(AutomationRun.id.desc()).limit(min(limit, 200))).all()


@router.get("/runs/{run_id}", response_model=AutomationRun)
def get_run(run_id: int, session: Session = Depends(get_session)):
    r = session.get(AutomationRun, run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r
