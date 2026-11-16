from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.settings_store import (GeneralSettings, default_location_map, get_general, get_location_map, get_scoring,
                                set_general, set_location_map, set_scoring)
from matcher.scoring import ScoringConfig
from matcher.service import rescore_all

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AllSettings(BaseModel):
    scoring: ScoringConfig
    general: GeneralSettings
    locations: dict[str, list[str]] = {}  # state -> towns/areas; empty on PUT means "leave unchanged"


@router.get("", response_model=AllSettings)
def read_settings(session: Session = Depends(get_session)):
    return AllSettings(scoring=get_scoring(session), general=get_general(session), locations=get_location_map(session))


@router.put("", response_model=AllSettings)
def update_settings(data: AllSettings, session: Session = Depends(get_session)):
    changed = data.scoring != get_scoring(session)
    set_scoring(session, data.scoring)
    set_general(session, data.general)
    if data.locations and data.locations != get_location_map(session):
        set_location_map(session, data.locations)
        changed = True
    if changed:
        rescore_all(session)
    return read_settings(session)


@router.get("/scoring/defaults", response_model=ScoringConfig)
def scoring_defaults():
    return ScoringConfig()


@router.get("/locations/defaults")
def locations_defaults() -> dict[str, list[str]]:
    return default_location_map()
