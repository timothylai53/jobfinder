"""JobStreet layout recognizer for pasted job pages.

A copied JobStreet job page has a fixed header block:

    <Company> logo            (alt text; not always present)
    <Title>
    <Company>
    <rating, e.g. 2.7>        (optional)
    View all jobs
    <Location> (Hybrid)       (work arrangement suffix optional)
    <Classification (Industry)>
    <Job type>
    <Salary | "Salary undisclosed">
    Posted 4d ago
    <badges: High application volume, Be an early applicant, ...>
    <JD body>
    Employer questions | Company profile | Report this job advert | Be careful ...
"""
import re

from sources.smart_paste import (
    JOB_TYPE,
    SALARY,
    PasteDraft,
    find_salary,
    is_nav,
    key,
    looks_like_location,
    looks_like_title,
    normalize_job_type,
    split_arrangement,
    tidy_description,
)

BADGES = {
    "high application volume", "be an early applicant", "actively hiring", "urgently hiring", "featured",
    "expiring soon", "new to you", "quick apply", "apply", "save", "saved", "share", "report this job",
}
END_MARKERS = re.compile(
    r"^(employer questions|your application will include|company profile|report this job advert|be careful|"
    r"what can i earn as|ask jobstreet|similar jobs|job seekers)\b",
    re.IGNORECASE,
)
_RATING = re.compile(r"^\d(\.\d)?(\s*·.*)?$")
_POSTED = re.compile(r"^(posted|reposted)\b.*\bago$|^posted on\b", re.IGNORECASE)


def _is_jobstreet(lines: list[str]) -> bool:
    keys = {key(row) for row in lines if row}
    hits = sum(k in keys for k in ("view all jobs", "employer questions", "report this job advert", "employer site",
                                   "salary undisclosed", "company profile"))
    return hits >= 2 or any(k in ("jobstreet", "jobstreet by seek") for k in keys) and "view all jobs" in keys


def recognize(raw_lines: list[str], names: list[str]) -> PasteDraft | None:
    if not _is_jobstreet(raw_lines):
        return None
    idx = [i for i, row in enumerate(raw_lines) if row]  # positions of non-blank lines
    nb = [raw_lines[i] for i in idx]

    # 1. Anchor: "<Company> logo", else the "View all jobs" link under the company name.
    title_at = None
    logo = next((i for i, row in enumerate(nb) if key(row).endswith(" logo") and i + 2 < len(nb)), None)
    view_all = next((i for i, row in enumerate(nb) if key(row) == "view all jobs"), None)
    if logo is not None:
        title_at = logo + 1
    elif view_all is not None:
        j = view_all - 1
        while j >= 0 and _RATING.match(nb[j]):
            j -= 1
        title_at = j - 1  # title is the line above the company
    if title_at is None or title_at < 0:
        return None

    d = PasteDraft(source="jobstreet")
    title, company = nb[title_at], nb[title_at + 1] if title_at + 1 < len(nb) else ""
    if not looks_like_title(title) or is_nav(company):
        return None
    d.title, d.company = title, company

    # 2. Header details after the company: skip rating / "View all jobs", read until "Posted …".
    i = title_at + 2
    while i < len(nb) and (_RATING.match(nb[i]) or key(nb[i]) == "view all jobs"):
        i += 1
    posted_at = None
    slot = 0
    while i < len(nb) and i < title_at + 12:
        line = nb[i]
        if _POSTED.match(line):
            posted_at = i
            break
        k = key(line)
        if slot == 0 and not JOB_TYPE.fullmatch(line) and not SALARY.search(line) and k != "salary undisclosed":
            d.location, d.work_arrangement = split_arrangement(line)
            if not looks_like_location(d.location, names):
                d.uncertain.append("location")
        elif JOB_TYPE.fullmatch(line):
            d.job_type = normalize_job_type(line)
        elif k == "salary undisclosed":
            d.salary_undisclosed = True  # explicitly no salary
        elif SALARY.search(line):
            d.salary_min, d.salary_max, d.salary_currency = find_salary(line)
        # anything else here is the classification line, e.g. "Engineering - Software (ICT)"
        slot += 1
        i += 1

    # 3. JD body: after "Posted …" and its badges, until the first end marker.
    if posted_at is None:
        d.uncertain += ["location", "job_type", "salary"]
        start = i
    else:
        start = posted_at + 1
    while start < len(nb) and key(nb[start]) in BADGES:
        start += 1
    end = next((j for j in range(start, len(nb)) if END_MARKERS.match(key(nb[j]))), len(nb))
    if start >= len(nb):
        return None
    body = raw_lines[idx[start]: idx[end] if end < len(nb) else len(raw_lines)]
    d.description = tidy_description(body)
    d.removed_lines = len(nb) - len([row for row in body if row.strip()])
    return d
