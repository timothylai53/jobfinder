from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Session

from app import config
from app.db import get_session
from export.backup import backup_db
from export.excel_csv import APP_COLUMNS, JOB_COLUMNS, application_rows, job_rows, to_csv, to_xlsx

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
