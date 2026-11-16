"""Rule-based quick score (0-100) with a fully explainable breakdown."""
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from matcher import requirements as reqs
from matcher import rules
from matcher.jd_sections import PREFERRED_PHRASES, is_requirements_section, section_type, split_clauses
from skills.matcher import SkillMatcher

MET, PARTIAL, NOT_MET, NOT_SPECIFIED = "met", "partial", "not_met", "not_specified"


class Weights(BaseModel):
    required_skills: float = Field(45, ge=0)
    preferred_skills: float = Field(15, ge=0)
    years: float = Field(20, ge=0)
    education: float = Field(10, ge=0)
    language_location: float = Field(10, ge=0)


class Gates(BaseModel):
    years_short_by: float = Field(2, ge=0, description="Gate when required years exceed mine by this much or more")
    cap: float = Field(40, ge=0, le=100, description="Max total when any gate fails")
    language: bool = True
    education: bool = True


LOW_CONFIDENCE_CAP = 50
NO_SKILLS = "Not enough information to assess skills"
THIN_SKILLS = 2  # at most this many skills found, and nothing else stated -> low confidence


class ScoringConfig(BaseModel):
    weights: Weights = Weights()
    gates: Gates = Gates()
    score_soft_skills: bool = False  # off: soft skills are listed but earn no points


@dataclass
class Candidate:
    """What the matcher knows about me."""
    years: float = 0
    education_level: str = ""
    education_field: str = ""
    degree_status: str = "completed"
    expected_graduation: str = ""
    education_source: str = ""  # bank item code ("B3") or "profile" the education came from
    languages: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    location_map: dict[str, list[str]] = field(default_factory=dict)  # state -> towns/areas
    remote_ok: bool = True
    skill_evidence: dict[str, list[str]] = field(default_factory=dict)  # skill -> ["B1", "profile", ...]


def _status(points: float, max_points: float) -> str:
    if points >= max_points - 1e-9:
        return MET
    return NOT_MET if points <= 1e-9 else PARTIAL


def _cat(key, label, points, max_points, items, note="", not_specified=False):
    points = round(points, 1)
    return {
        "key": key, "label": label, "points": points, "max": max_points,
        "status": NOT_SPECIFIED if not_specified else _status(points, max_points),
        "not_specified": not_specified, "note": note, "items": items,
    }


def _req_item(r: reqs.Requirement, cand: Candidate, matcher: SkillMatcher) -> tuple[dict, bool]:
    direct, equivalent = reqs.evidence_for(r, cand.skill_evidence, matcher)
    have = direct or equivalent
    name = ("One of: " + " / ".join(r.skills)) if r.is_group else r.skills[0]
    if r.equivalent_ok:
        name += " (or equivalent)"
    if direct:
        detail = "; ".join(f"{s}, from {', '.join(cand.skill_evidence[s])}" for s in direct) if r.is_group             else "from " + ", ".join(cand.skill_evidence[direct[0]])
    elif equivalent:
        detail = "equivalent: " + "; ".join(f"{s}, from {', '.join(cand.skill_evidence[s])}" for s in equivalent)
    else:
        detail = "none of these in Experience Bank or profile" if r.is_group else "not in Experience Bank or profile"
    ev = [e for s in (direct or equivalent) for e in cand.skill_evidence[s]]
    return {"name": name, "status": MET if have else NOT_MET, "evidence": list(dict.fromkeys(ev)), "detail": detail,
            "group": r.skills if r.is_group else []}, bool(have)


def _skills_category(key, label, wanted: list[reqs.Requirement], cand: Candidate, matcher: SkillMatcher,
                     max_points: float):
    if not wanted:
        return _cat(key, label, max_points, max_points, [], "JD lists no skills in this category", True)
    items, matched = [], 0
    for r in wanted:
        item, ok = _req_item(r, cand, matcher)
        matched += ok
        items.append(item)
    note = f"{matched} of {len(wanted)} matched"
    return _cat(key, label, max_points * matched / len(wanted), max_points, items, note)


def _has_requirements_section(clauses) -> bool:
    """A Requirements / Qualifications section exists. Without one, the ad never says what is required, so the
    skills found under duties (or no heading) are what the job needs (decision #113)."""
    return any(is_requirements_section(c.section) for c in clauses)


def collect_requirements(clauses, matcher: SkillMatcher, score_soft: bool):
    """Required / preferred requirements (deduplicated) and soft skills, from classified clauses."""
    required: list[reqs.Requirement] = []
    preferred: list[reqs.Requirement] = []
    soft: dict[str, str] = {}  # skill -> "required" / "preferred" (required wins)
    promote = not _has_requirements_section(clauses)
    for c in clauses:
        if c.kind == "ignored":
            continue
        found = reqs.from_clause(c.text, matcher, score_soft)
        kind = c.kind
        if promote and kind == "preferred" and section_type(c.section) != "preferred" and not PREFERRED_PHRASES.search(c.text):
            kind = "required"  # no requirements section: duties count; "nice to have" sections and "is a plus" don't
        target = required if kind == "required" else preferred
        for r in found.hard:
            if r.key not in {x.key for x in target}:
                target.append(r)
        for sk in found.soft:
            if soft.get(sk) != "required":
                soft[sk] = c.kind
    req_skills = {sk for r in required for sk in r.skills}
    preferred = [r for r in preferred if not set(r.skills) <= req_skills and r.key not in {x.key for x in required}]
    return required, preferred, soft


def score_job(jd: str, job_location: str, cand: Candidate, matcher: SkillMatcher,
              config: ScoringConfig | None = None) -> dict:
    cfg = config or ScoringConfig()
    w, g = cfg.weights, cfg.gates
    clauses = split_clauses(jd)
    gates: list[dict] = []

    # 1-2. skills, split into required vs preferred (required wins when both). A clause listing
    # alternatives ("C#/ Java/ Javascript") is one requirement met by any of them. Soft skills are
    # listed separately and earn no points unless score_soft_skills is on.
    required, preferred, soft = collect_requirements(clauses, matcher, cfg.score_soft_skills)
    no_skills = not required and not preferred  # the JD names no dictionary skill at all (soft skills don't count)
    if no_skills:  # an empty skills list is missing information, not a perfect match
        categories = [_cat("required_skills", "Required skills", 0, w.required_skills, [], NO_SKILLS, True)]
    else:
        categories = [_skills_category("required_skills", "Required skills", required, cand, matcher, w.required_skills)]
    categories.append(_skills_category("preferred_skills", "Preferred skills", preferred, cand, matcher, w.preferred_skills))
    soft_items = [{"name": sk, "kind": kind, "status": MET if cand.skill_evidence.get(sk) else NOT_MET,
                   "evidence": cand.skill_evidence.get(sk, []),
                   "detail": ("from " + ", ".join(cand.skill_evidence[sk])) if cand.skill_evidence.get(sk) else "not claimed"}
                  for sk, kind in soft.items()]

    # 3a. years of experience
    yr = rules.extract_years(clauses)
    if yr.years is None:
        categories.append(_cat("years", "Years of experience", w.years, w.years, [], "JD does not state years", True))
    else:
        short = yr.years - cand.years
        if short <= 0:
            pts, st = w.years, MET
        elif short < g.years_short_by:
            pts, st = w.years / 2, PARTIAL
        else:
            pts, st = 0, NOT_MET
            gates.append({"key": "years", "message": f"Requires {yr.years:g} years; you have {cand.years:g} (short by {short:g})"})
        label = "fresh graduates welcome" if yr.fresh_grad_ok else f"{yr.years:g}+ years required"
        detail = f"{label}; you have {cand.years:g}"
        categories.append(_cat("years", "Years of experience", pts, w.years,
                               [{"name": label, "status": st, "detail": detail, "evidence": [yr.evidence]}], detail))

    # 3b. education
    categories.append(_education(rules.extract_education(clauses), cand, w.education, g, gates))

    # 3c. language + location (half each)
    categories.append(_language_location(clauses, jd, job_location, cand, w.language_location, g, gates))

    raw_total = sum(c["points"] for c in categories)
    max_total = sum(c["max"] for c in categories) or 1
    total = round(100 * raw_total / max_total)
    capped = bool(gates) and total > g.cap
    if gates:
        total = min(total, int(g.cap))
    found = {sk for r in [*required, *preferred] for sk in r.skills}
    others_unstated = all(c["not_specified"] for c in categories if c["key"] in ("years", "education", "language_location"))
    if no_skills:
        low = f"{NO_SKILLS}: the JD names no skills from the dictionary"
    elif len(found) <= THIN_SKILLS and others_unstated:
        low = (f"Thin evidence: only {len(found)} skill(s) found ({', '.join(sorted(found))}) and the JD states "
               "no years, education, language or location")
    else:
        low = ""
    if low and total > LOW_CONFIDENCE_CAP:
        total, capped = LOW_CONFIDENCE_CAP, True
    return {
        "total": total,
        "low_confidence": low,
        "raw_total": round(100 * raw_total / max_total, 1),
        "capped": capped,
        "gates": gates,
        "categories": categories,
        "required_skills": list(dict.fromkeys(sk for r in required for sk in r.skills)),
        "preferred_skills": list(dict.fromkeys(sk for r in preferred for sk in r.skills)),
        "soft_skills": soft_items,
    }


def _education(req: rules.EducationRequirement, cand: Candidate, max_points: float, g: Gates, gates: list) -> dict:
    if req.level is None:
        return _cat("education", "Education", max_points, max_points, [], "JD does not state education", True)
    my_rank = rules.EDU_LEVELS.get(cand.education_level, 0)
    need = rules.EDU_LEVELS[req.level]
    in_progress = cand.degree_status == "in_progress"
    mine = cand.education_level or "not set"
    if in_progress and cand.education_level:
        grad = f", expected {cand.expected_graduation}" if cand.expected_graduation else ""
        mine = f"{cand.education_level} (in progress{grad})"
    if cand.education_level and cand.education_source:
        mine += f", from {cand.education_source}"

    items = []
    if my_rank >= need and not in_progress:
        level_factor, lst = 1.0, MET
    elif my_rank >= need and in_progress:
        level_factor, lst = 0.5, PARTIAL
    else:
        level_factor, lst = 0.0, NOT_MET
    items.append({"name": f"{req.level} or higher", "status": lst, "detail": f"you have {mine}", "evidence": [req.evidence]})
    if lst == NOT_MET and req.mandatory and g.education:
        gates.append({"key": "education", "message": f"Requires {req.level}; you have {mine}"})

    field_factor = 1.0
    fm = rules.field_matches(cand.education_field, req)
    if fm is not None:
        field_factor = 1.0 if fm else 0.5
        items.append({"name": "Field: " + ", ".join(req.fields) + (" (or related)" if req.related_ok else ""),
                      "status": MET if fm else PARTIAL,
                      "detail": f"your field: {cand.education_field or 'not set'}", "evidence": [req.evidence]})
    note = f"needs {req.level}{'' if req.mandatory else ' (preferred)'}; you have {mine}"
    return _cat("education", "Education", max_points * level_factor * field_factor, max_points, items, note)


def _language_location(clauses, jd, job_location, cand: Candidate, max_points: float, g: Gates, gates: list) -> dict:
    half = max_points / 2
    items = []
    mine = {rules.normalize_language(l) or l for l in cand.languages}

    langs = rules.extract_languages(clauses)
    if langs:
        have = 0
        for lr in langs:
            ok = lr.language in mine
            have += ok
            items.append({"name": f"{lr.language} ({'required' if lr.mandatory else 'preferred'})",
                          "status": MET if ok else NOT_MET,
                          "detail": "you speak it" if ok else "not in your profile languages",
                          "evidence": [lr.evidence]})
            if not ok and lr.mandatory and g.language:
                gates.append({"key": "language", "message": f"Mandatory language missing: {lr.language}"})
        lang_pts = half * have / len(langs)
    else:
        lang_pts = half
        items.append({"name": "Languages", "status": NOT_SPECIFIED, "detail": "JD does not state languages", "evidence": []})

    remote = rules.is_remote(job_location, jd)
    if remote and cand.remote_ok:
        loc_pts = half
        items.append({"name": "Location: remote", "status": MET, "detail": "remote role and you accept remote", "evidence": []})
    elif not job_location.strip() or not [p for p in cand.preferred_locations if p.strip().lower() != "remote"]:
        loc_pts = half
        why = "job location unknown" if not job_location.strip() else "no preferred locations set"
        items.append({"name": f"Location: {job_location or 'unknown'}", "status": NOT_SPECIFIED, "detail": why, "evidence": []})
    else:
        hit = rules.location_matches(job_location, cand.preferred_locations, cand.location_map)
        loc_pts = half if hit else 0
        if hit:
            pref, found = hit
            how = pref if found.lower() == pref.strip().lower() else f"{pref} ({found})"
        items.append({"name": f"Location: {job_location}", "status": MET if hit else NOT_MET,
                      "detail": f"matches {how}" if hit else "not in your preferred locations: " + ", ".join(cand.preferred_locations),
                      "evidence": []})
    not_spec = not langs and all(i["status"] == NOT_SPECIFIED for i in items)
    met_n = sum(i["status"] == MET for i in items)
    return _cat("language_location", "Language + location", lang_pts + loc_pts, max_points, items,
                f"{met_n} of {len(items)} met", not_spec)
