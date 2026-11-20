"""Jobs + scores + applications as rows, written to .xlsx (two sheets) or .csv."""
import csv
import io

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from sqlmodel import Session, select

from models import Application, Job, MatchResult

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
    for j in session.exec(select(Job).order_by(Job.id)).all():
        m, a = scores.get(j.id), apps.get(j.id)
        d = j.model_dump()
        d.update(score=m.total if m else None, gates=m.gate_flags if m else [],
                 application_status=a.status if a else "")
        rows.append({c: _cell(d.get(c)) for c in JOB_COLUMNS})
    return rows


def application_rows(session: Session) -> list[dict]:
    jobs = {j.id: j for j in session.exec(select(Job)).all()}
    scores = {m.job_id: m.total for m in session.exec(select(MatchResult).where(MatchResult.method == "quick")).all()}
    rows = []
    for a in session.exec(select(Application).order_by(Application.id)).all():
        j = jobs.get(a.job_id)
        d = a.model_dump()
        d.update(job_title=j.title if j else "", company=j.company if j else "", score=scores.get(a.job_id))
        rows.append({c: _cell(d.get(c)) for c in APP_COLUMNS})
    return rows


def to_xlsx(session: Session) -> bytes:
    wb = Workbook()
    for idx, (title, cols, rows) in enumerate((("Jobs", JOB_COLUMNS, job_rows(session)),
                                               ("Applications", APP_COLUMNS, application_rows(session)))):
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = title
        ws.append(cols)
        for r in rows:
            ws.append([r[c] for c in cols])
        ws.freeze_panes = "A2"
        for i, c in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(i)].width = max(10, min(45, len(c) + 4))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(rows: list[dict], columns: list[str]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns)
    w.writeheader()
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly
