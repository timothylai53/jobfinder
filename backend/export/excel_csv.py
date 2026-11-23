"""Jobs + scores + applications as rows, written to .xlsx (two sheets) or .csv."""
import csv
import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlmodel import Session, col, select

from models import Application, Job, MatchResult
from models._base import require_id

JOB_COLUMNS = ["id", "title", "company", "location", "work_arrangement", "score", "gates", "salary_min", "salary_max",
               "salary_currency", "job_type", "posted_date", "sources", "urls", "hidden", "hidden_reason",
               "fetched_at", "application_status"]
APP_COLUMNS = ["id", "job_id", "job_title", "company", "status", "applied_at", "follow_up_at", "score", "notes",
               "created_at", "updated_at"]


# Text that a spreadsheet would run as a formula (CSV / formula injection, OWASP). Job titles and descriptions come
# from untrusted ads, so a title like =HYPERLINK("http://evil","Click") must stay text when Excel opens the export.
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def _text(s: str) -> str:
    return "'" + s if s.startswith(FORMULA_START) else s


def _cell(v):
    if isinstance(v, list):
        return _text(", ".join(str(x) for x in v))
    if v is None:
        return ""
    return v if isinstance(v, (int, float, bool)) else _text(str(v))


def job_rows(session: Session) -> list[dict]:
    scores = {m.job_id: m for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    apps = {a.job_id: a for a in session.exec(select(Application)).all()}
    rows = []
    for j in session.exec(select(Job).order_by(col(Job.id))).all():
        m, a = scores.get(require_id(j)), apps.get(require_id(j))
        d = j.model_dump()
        d.update(score=m.total if m else None, gates=m.gate_flags if m else [],
                 application_status=a.status if a else "")
        rows.append({c: _cell(d.get(c)) for c in JOB_COLUMNS})
    return rows


def application_rows(session: Session) -> list[dict]:
    jobs = {j.id: j for j in session.exec(select(Job)).all()}
    scores = {m.job_id: m.total for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    rows = []
    for a in session.exec(select(Application).order_by(col(Application.id))).all():
        j = jobs.get(a.job_id)
        d = a.model_dump()
        d.update(job_title=j.title if j else "", company=j.company if j else "", score=scores.get(a.job_id))
        rows.append({c: _cell(d.get(c)) for c in APP_COLUMNS})
    return rows


# Excel gets readable headers; the CSV files keep the field names (stable for scripts that read them).
LABELS = {
    "id": "ID", "title": "Title", "company": "Company", "location": "Location", "work_arrangement": "Work arrangement",
    "score": "Score", "gates": "Hard requirements missed", "salary_min": "Salary min", "salary_max": "Salary max",
    "salary_currency": "Currency", "job_type": "Job type", "posted_date": "Posted", "sources": "Sources", "urls": "Links",
    "hidden": "Hidden", "hidden_reason": "Hidden because", "fetched_at": "Added", "application_status": "Tracker status",
    "job_id": "Job ID", "job_title": "Job", "status": "Status", "applied_at": "Applied on", "follow_up_at": "Follow up on",
    "notes": "Notes", "created_at": "Created", "updated_at": "Last changed",
}
DATE_COLUMNS = {"posted_date", "applied_at", "follow_up_at"}
DATETIME_COLUMNS = {"fetched_at", "created_at", "updated_at"}


def _excel_value(column: str, value):
    """Dates and timestamps as real Excel dates (sortable, filterable), in local time; everything else as is."""
    if not isinstance(value, str) or not value:
        return value
    try:
        if column in DATE_COLUMNS:
            return date.fromisoformat(value[:10])
        if column in DATETIME_COLUMNS:
            moment = datetime.fromisoformat(value)
            if moment.tzinfo is not None:  # stored in UTC: show the laptop's local time, as the app does
                moment = moment.astimezone().replace(tzinfo=None)
            return moment.replace(microsecond=0)
    except ValueError:
        return value
    return value


def to_xlsx(session: Session) -> bytes:
    wb = Workbook()
    bold = Font(bold=True)
    for idx, (title, cols, rows) in enumerate((("Jobs", JOB_COLUMNS, job_rows(session)),
                                               ("Applications", APP_COLUMNS, application_rows(session)))):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = title
        ws.append([LABELS.get(c, c) for c in cols])
        for cell in ws[1]:
            cell.font = bold
        for r in rows:
            ws.append([_excel_value(c, r[c]) for c in cols])
        for i, c in enumerate(cols, 1):
            letter = get_column_letter(i)
            if c in DATE_COLUMNS or c in DATETIME_COLUMNS:
                for (cell,) in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                    if isinstance(cell.value, datetime):
                        cell.number_format = "dd mmm yyyy, h:mm AM/PM" if c in DATETIME_COLUMNS else "dd mmm yyyy"
                    elif isinstance(cell.value, date):
                        cell.number_format = "dd mmm yyyy"
            # Wide enough for the header and the typical value; long text (titles, links, notes) is capped.
            longest = max([len(LABELS.get(c, c))] + [len(str(r[c])) for r in rows[:200]])
            if c in DATETIME_COLUMNS:
                longest = max(longest, 20)
            ws.column_dimensions[letter].width = max(8, min(50, longest + 2))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(rows: list[dict], columns: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns)
    w.writeheader()
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly
