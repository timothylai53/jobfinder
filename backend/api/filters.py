from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from app.db import get_session
from filters.service import reapply_all
from models import FILTER_TYPES, FilterRule, FilterRuleBase

router = APIRouter(prefix="/api/filters", tags=["filters"])


def _validate(data: FilterRuleBase) -> None:
    if data.type not in FILTER_TYPES:
        raise HTTPException(422, f"type must be one of {', '.join(FILTER_TYPES)}")
    if not data.value.strip():
        raise HTTPException(422, "value is required")
    if data.type in ("min_years_over", "min_salary_below"):
        try:
            float(data.value)
        except ValueError as e:
            raise HTTPException(422, "value must be a number for this rule type") from e


@router.get("", response_model=list[FilterRule])
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(FilterRule).order_by(col(FilterRule.id))).all()


@router.post("", response_model=FilterRule)
def create_rule(data: FilterRuleBase, session: Session = Depends(get_session)):
    _validate(data)
    r = FilterRule(**data.model_dump())
    session.add(r)
    session.commit()
    reapply_all(session)
    session.refresh(r)
    return r


@router.put("/{rule_id}", response_model=FilterRule)
def update_rule(rule_id: int, data: FilterRuleBase, session: Session = Depends(get_session)):
    r = session.get(FilterRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    _validate(data)
    for k, v in data.model_dump().items():
        setattr(r, k, v)
    session.commit()
    reapply_all(session)
    session.refresh(r)
    return r


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, session: Session = Depends(get_session)):
    r = session.get(FilterRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    session.delete(r)
    session.commit()
    reapply_all(session)
    return {"ok": True}
