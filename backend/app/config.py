"""Paths and constants. JOBFINDER_DATA_DIR overrides the data folder (used by tests)."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("JOBFINDER_DATA_DIR", PROJECT_ROOT / "data"))
DB_PATH = DATA_DIR / "jobfinder.db"
UPLOADS_DIR = DATA_DIR / "uploads"
BACKUPS_DIR = DATA_DIR / "backups"

USER_AGENT = "JobFinder/0.1 (personal job search tool; single user)"


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOADS_DIR, BACKUPS_DIR):
        d.mkdir(parents=True, exist_ok=True)
