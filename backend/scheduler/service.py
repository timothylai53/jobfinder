"""APScheduler, started with the backend. Daily automations run at their HH:MM (local time).

Catch-up: automations only run while the app is running. On startup, every enabled, scheduled daily
automation whose last due time passed without a run is run once (in the background).
JOBFINDER_NO_SCHEDULER=1 disables it (tests).
"""
import os
import re
import threading
from datetime import datetime, time, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from models import Automation
from scheduler.automations import run_automation

_DAILY = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def is_daily(schedule: str) -> bool:
    return bool(_DAILY.match(schedule or ""))


def last_due(schedule: str, now_local: datetime) -> datetime | None:
    """The most recent moment this daily schedule was due, in local time."""
    m = _DAILY.match(schedule or "")
    if not m:
        return None
    due = datetime.combine(now_local.date(), time(int(m.group(1)), int(m.group(2))), tzinfo=now_local.tzinfo)
    return due if now_local >= due else due - timedelta(days=1)


def missed(auto: Automation, now_local: datetime) -> bool:
    if not (auto.enabled and auto.mode == "scheduled" and is_daily(auto.schedule)):
        return False
    due = last_due(auto.schedule, now_local)
    if auto.last_run_at is None:
        return True
    last = auto.last_run_at if auto.last_run_at.tzinfo else auto.last_run_at.replace(tzinfo=now_local.tzinfo)
    return last.astimezone(now_local.tzinfo) < due


class AutomationScheduler:
    def __init__(self, engine):
        self.engine = engine
        self.sched = BackgroundScheduler()

    def start(self) -> None:
        self.sched.start()
        self.reschedule()
        threading.Thread(target=self.catch_up, name="automation-catch-up", daemon=True).start()

    def shutdown(self) -> None:
        if self.sched.running:
            self.sched.shutdown(wait=False)

    def reschedule(self) -> None:
        self.sched.remove_all_jobs()
        with Session(self.engine) as s:
            for a in s.exec(select(Automation)).all():
                a.next_run_at = None
                if a.enabled and a.mode == "scheduled" and is_daily(a.schedule):
                    hh, mm = a.schedule.split(":")
                    job = self.sched.add_job(run_automation, CronTrigger(hour=int(hh), minute=int(mm)),
                                             args=[self.engine, a.key, "schedule"], id=a.key, replace_existing=True,
                                             misfire_grace_time=3600, coalesce=True)
                    a.next_run_at = getattr(job, "next_run_time", None)
            s.commit()

    def catch_up(self) -> list[str]:
        now_local = datetime.now().astimezone()
        with Session(self.engine) as s:
            todo = [a.key for a in s.exec(select(Automation)).all() if missed(a, now_local)]
        for key in todo:
            run_automation(self.engine, key, "catch-up")
        return todo


_scheduler: AutomationScheduler | None = None


def start(engine) -> AutomationScheduler | None:
    global _scheduler
    if os.environ.get("JOBFINDER_NO_SCHEDULER") == "1":
        return None
    _scheduler = AutomationScheduler(engine)
    _scheduler.start()
    return _scheduler


def reschedule() -> None:
    if _scheduler is not None:
        _scheduler.reschedule()


def stop() -> None:
    if _scheduler is not None:
        _scheduler.shutdown()
