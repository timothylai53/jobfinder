"""Source plugin interface. Every source turns a SearchProfile into NormalizedJobs."""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class NormalizedJob:
    title: str
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    source: str = "manual"
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    job_type: str = ""
    work_arrangement: str = ""
    posted_date: date | None = None
    extra: dict = field(default_factory=dict)


class Source(Protocol):
    key: str

    def fetch(self, search_profile) -> list[NormalizedJob]: ...


_COMPANY_SUFFIX = re.compile(
    r"\b(sdn\.?\s*bhd\.?|bhd\.?|berhad|plc|pte\.?\s*ltd\.?|ltd\.?|limited|inc\.?|llc|corp(oration)?\.?|co\.)",
    re.IGNORECASE,
)
_TITLE_NOISE = re.compile(r"\(.*?\)|\[.*?\]|\b(urgent(ly)?|hiring|immediate|wanted|new)\b", re.IGNORECASE)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def dedupe_key(company: str, title: str, location: str = "") -> str:
    """Fuzzy key: normalized company | title | first location token."""
    c = _slug(_COMPANY_SUFFIX.sub("", company or ""))
    t = _slug(_TITLE_NOISE.sub("", title or ""))
    t = re.sub(r"\b(jr|junior)\b", "junior", t)
    t = re.sub(r"\b(sr|senior)\b", "senior", t)
    t = re.sub(r"\b(engineer|developer|programmer)\b", "dev", t)
    loc = _slug((location or "").split(",")[0])
    return f"{c}|{t}|{loc}"


_STATE_CODE = re.compile(r"^[A-Z]{1,2}\d{1,3}$")  # Indeed's region codes, e.g. "M14"


def tidy_location(loc: str) -> str:
    """"Kuala Lumpur, M14, Malaysia" -> "Kuala Lumpur". A lone "Malaysia" is kept (it's all we know)."""
    parts = [p.strip() for p in (loc or "").split(",") if p.strip()]
    parts = [p for p in parts if not _STATE_CODE.match(p)]
    if len(parts) > 1 and parts[-1].lower() == "malaysia":
        parts = parts[:-1]
    return ", ".join(parts)


def _loc_parts(loc: str) -> list[str]:
    parts = [_slug(p) for p in tidy_location(loc).split(",")]
    return [p for p in parts if p and p not in ("malaysia", "my")]


def locations_compatible(a: str, b: str) -> bool:
    """Same place, written differently by two sites? ("Kuala Lumpur City Centre, Kuala Lumpur" vs
    "Kuala Lumpur, Federal Territory of Kuala Lumpur"). Unknown locations are compatible with anything."""
    pa, pb = _loc_parts(a), _loc_parts(b)
    if not pa or not pb:
        return True
    within = lambda x, y: re.search(rf"(?<![a-z0-9]){re.escape(x)}(?![a-z0-9])", y) is not None  # noqa: E731
    return any(within(x, y) or within(y, x) for x in pa for y in pb)
