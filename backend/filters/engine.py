"""Pure filter-rule evaluation. A rule that matches hides the job, with a readable reason."""
import re
from dataclasses import dataclass

from matcher.jd_sections import split_clauses
from matcher.rules import extract_years


@dataclass
class Rule:
    id: int | None
    type: str
    value: str
    enabled: bool = True


@dataclass
class JobView:
    title: str
    company: str
    description: str
    salary_min: float | None = None
    salary_max: float | None = None


def _terms(value: str) -> list[str]:
    return [t.strip() for t in value.split(",") if t.strip()]


def _word(term: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def _allowed(term: str) -> re.Pattern:
    """Allow-list term: 2 letters or fewer ("IT", "QA") must be a whole word; longer ones may start a word,
    so "test" also allows "Tester" / "Testing" and "engineer" allows "Engineering"."""
    tail = r"(?![A-Za-z0-9])" if len(term) <= 2 else ""
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(term) + tail, re.IGNORECASE)


def _norm_company(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(sdn\.?\s*bhd\.?|bhd\.?|berhad|plc|pte\.?\s*ltd\.?|ltd\.?|inc\.?|llc|corp\.?|co\.)", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def check_rule(rule: Rule, job: JobView) -> str | None:
    """Return the hide reason if the rule matches, else None."""
    t = rule.type
    if t == "title_contains":
        hit = next((x for x in _terms(rule.value) if _word(x).search(job.title or "")), None)
        return f'Title contains "{hit}"' if hit else None
    if t == "title_must_contain_one_of":
        terms = _terms(rule.value)
        if not terms or any(_allowed(x).search(job.title or "") for x in terms):
            return None
        return "Title has none of: " + ", ".join(terms)
    if t == "company_equals":
        hit = next((x for x in _terms(rule.value) if _norm_company(x) == _norm_company(job.company or "")), None)
        return f"Company is {hit}" if hit else None
    if t == "keyword_in_jd":
        hit = next((x for x in _terms(rule.value) if _word(x).search(job.description or "")), None)
        return f'JD mentions "{hit}"' if hit else None
    if t == "min_years_over":
        limit = float(rule.value)
        yrs = extract_years(split_clauses(job.description or "")).years
        return f"Requires {yrs:g} years (> {limit:g})" if yrs is not None and yrs > limit else None
    if t == "min_salary_below":
        limit = float(rule.value)
        best = job.salary_max if job.salary_max is not None else job.salary_min
        return f"Salary {best:g} below {limit:g}" if best is not None and best < limit else None
    raise ValueError(f"Unknown filter type: {t}")


def evaluate(rules: list[Rule], job: JobView) -> str | None:
    reasons = [r for r in (check_rule(rule, job) for rule in rules if rule.enabled) if r]
    return "; ".join(reasons) if reasons else None
