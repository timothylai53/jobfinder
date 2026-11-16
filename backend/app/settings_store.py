"""Typed access to AppSetting rows (key/value JSON)."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from matcher.scoring import ScoringConfig
from models import AppSetting


class GeneralSettings(BaseModel):
    follow_up_days: int = Field(7, ge=1, le=90)
    high_match_threshold: int = Field(70, ge=0, le=100)
    resume_projects_first: bool = True  # PDF section order: Projects before Experience (fresh-grad layout)


class AISettings(BaseModel):
    """AI mode (brief §6.6): copy_paste (default), ollama, or off. There is no paid provider."""
    mode: Literal["copy_paste", "ollama", "off"] = "copy_paste"
    ollama_model: str = "qwen2.5:3b"  # small default for a 3 GB GPU; any installed model can be chosen
    ollama_timeout_s: int = Field(300, ge=30, le=1800)
    auto_analysis_max_per_run: int = Field(3, ge=1, le=20)  # ollama_deep_analysis automation


def _get(session: Session, key: str):
    row = session.get(AppSetting, key)
    return row.value if row else None


def _put(session: Session, key: str, value) -> None:
    row = session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    session.commit()


def get_scoring(session: Session) -> ScoringConfig:
    return ScoringConfig.model_validate(_get(session, "scoring") or {})


def set_scoring(session: Session, cfg: ScoringConfig) -> None:
    _put(session, "scoring", cfg.model_dump())


def get_ai(session: Session) -> AISettings:
    return AISettings.model_validate(_get(session, "ai") or {})


def set_ai(session: Session, cfg: AISettings) -> None:
    _put(session, "ai", cfg.model_dump())


def get_general(session: Session) -> GeneralSettings:
    return GeneralSettings.model_validate(_get(session, "general") or {})


def set_general(session: Session, cfg: GeneralSettings) -> None:
    _put(session, "general", cfg.model_dump())


LOCATIONS_SEED = Path(__file__).resolve().parents[1] / "matcher" / "locations_seed.json"


def default_location_map() -> dict[str, list[str]]:
    return json.loads(LOCATIONS_SEED.read_text(encoding="utf-8"))


def get_location_map(session: Session) -> dict[str, list[str]]:
    """State -> towns/areas used for location matching. Seeded from locations_seed.json until edited."""
    v = _get(session, "location_map")
    return v if isinstance(v, dict) else default_location_map()


def set_location_map(session: Session, value: dict[str, list[str]]) -> None:
    clean = {}
    for state, towns in value.items():
        if state.strip():
            clean[state.strip()] = list(dict.fromkeys(t.strip() for t in towns if t.strip()))
    _put(session, "location_map", clean)


def next_item_code(session: Session) -> str:
    """Stable Experience Bank IDs (B1, B2, ...); numbers are never reused."""
    n = int(_get(session, "next_item_number") or 1)
    row = session.get(AppSetting, "next_item_number")
    if row:
        row.value = n + 1
    else:
        session.add(AppSetting(key="next_item_number", value=n + 1))
    session.flush()
    return f"B{n}"
