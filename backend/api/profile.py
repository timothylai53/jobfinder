from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from matcher.service import effective_education, get_profile, rescore_all
from models import Profile, ProfileBase

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=Profile)
def read_profile(session: Session = Depends(get_session)):
    return get_profile(session)


@router.put("", response_model=Profile)
def update_profile(data: ProfileBase, session: Session = Depends(get_session)):
    p = get_profile(session)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    session.add(p)
    session.commit()
    rescore_all(session)
    session.refresh(p)
    return p


@router.get("/status")
def profile_status(session: Session = Depends(get_session)):
    """Education the matcher will use, and the key fields still missing (each with where to fix it)."""
    p = get_profile(session)
    edu = effective_education(session, p)
    missing = []
    if not edu:
        missing.append({"key": "education_level", "label": "education level", "fix": "/resume",
                        "hint": "Add your education to the Experience Bank or set it in your profile."})
    elif not edu.field:
        missing.append({"key": "education_field", "label": "field of study", "fix": "/settings?section=profile",
                        "hint": "Without it, education points for “Degree in Computer Science or related” can't be checked."})
    if not p.preferred_locations:
        missing.append({"key": "preferred_locations", "label": "preferred locations", "fix": "/settings?section=locations",
                        "hint": "Without them, every job gets full location points."})
    if not p.years_confirmed:
        missing.append({"key": "years_of_experience", "label": "years of experience", "fix": "/settings?section=profile",
                        "hint": "Confirm it, even if it is 0."})
    return {
        "education": None if not edu else {
            "level": edu.level, "field": edu.field, "in_progress": edu.in_progress,
            "expected": edu.expected, "source": edu.source,
        },
        "missing": missing,
    }
