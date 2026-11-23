from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app import config
from app.db import create_db, engine, get_session
from export.backup import BackupError, backup_db, backup_status, list_backups, restore_backup
from export.excel_csv import APP_COLUMNS, JOB_COLUMNS, application_rows, job_rows, to_csv, to_xlsx
from matcher.service import rescore_all

router = APIRouter(prefix="/api", tags=["export"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _download(data: bytes, media: str, name: str) -> Response:
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/xlsx")
def export_xlsx(session: Session = Depends(get_session)):
    return _download(to_xlsx(session), XLSX, f"jobfinder-{datetime.now():%Y%m%d}.xlsx")


@router.get("/export/{kind}.csv")
def export_csv(kind: str, session: Session = Depends(get_session)):
    if kind == "jobs":
        data = to_csv(job_rows(session), JOB_COLUMNS)
    elif kind == "applications":
        data = to_csv(application_rows(session), APP_COLUMNS)
    else:
        raise HTTPException(404, "Use jobs.csv or applications.csv")
    return _download(data, "text/csv; charset=utf-8", f"jobfinder-{kind}-{datetime.now():%Y%m%d}.csv")


@router.post("/backup")
def backup():
    dest = backup_db(config.DB_PATH, config.BACKUPS_DIR)
    return {"path": str(dest), "name": dest.name}


@router.get("/backup/status")
def backup_info():
    """Last backup (manual or automatic) and how many automatic daily backups are kept."""
    return backup_status(config.BACKUPS_DIR)


@router.get("/backups")
def backups():
    """Every backup, newest first."""
    return list_backups(config.BACKUPS_DIR)


@router.post("/backups/{name}/restore")
def restore(name: str, session: Session = Depends(get_session)):
    """Replace the current data with a backup. The current data is saved as a backup first; an older backup's schema
    is brought up to date, and every job is rescored with today's rules."""
    session.close()
    engine.dispose()  # no pooled connection keeps the old file state while it is replaced
    try:
        saved = restore_backup(name, config.DB_PATH, config.BACKUPS_DIR)
    except BackupError as e:
        raise HTTPException(422, str(e)) from e
    create_db()  # new tables and columns for a backup made by an older version
    with Session(engine) as s:
        rescored = rescore_all(s)
    return {"restored": name, "saved_current_as": saved.name, "rescored": rescored}
