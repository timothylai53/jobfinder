"""JobStreet (SEEK) source: the public, logged-out endpoints the website itself calls.

- search: GET  https://<host>/api/jobsearch/v5/search  -> job cards (id, title, company, location, ...)
- detail: POST https://<host>/graphql (jobDetails)     -> full job description (HTML)
          (the job web page is never requested: it answered 403 in the 13 Nov smoke test)

Both shapes are read defensively: every field is optional, and a response without the expected
structure raises SchemaChanged (the source shows "error: schema changed") instead of crashing.
The exact shapes are confirmed in the supervised smoke test (Phase 2 plan, option B).
"""
import re
import uuid
from datetime import UTC, datetime, timedelta

from sources.base import NormalizedJob
from sources.http import PoliteClient, RateLimited, SchemaChanged, SourceError, save_debug
from sources.ingest import SUMMARY_ONLY
from sources.manual import clean_text
from sources.smart_paste import arrangement_label, find_salary, normalize_job_type

# country code -> (host, siteKey, locale, timezone). Malaysia first; more countries = more rows.
SITES = {"MY": ("my.jobstreet.com", "MY-Main", "en-MY", "Asia/Kuala_Lumpur")}
PAGE_SIZE = 30
MAX_PAGES_PER_QUERY = 2  # only when the cap is above one page: a cap <= 30 means 1 search per query

JOB_DETAILS_QUERY = """query jobDetails($jobId: ID!, $jobDetailsViewedCorrelationId: String!, $sessionId: String!,
 $zone: Zone!, $locale: Locale!, $languageCode: LanguageCodeIso!, $countryCode: CountryCodeIso2!, $timezone: Timezone!) {
  jobDetails(id: $jobId, tracking: {channel: "WEB", jobDetailsViewedCorrelationId: $jobDetailsViewedCorrelationId,
   sessionId: $sessionId}) {
    job { id title content(platform: WEB) advertiser { name(locale: $locale) } location { label(locale: $locale, type: LONG) }
      workTypes { label(locale: $locale) } workArrangements { arrangements { label(locale: $locale) } }
      salary { label currencyLabel(zone: $zone) } listedAt { dateTimeUtc } }
  }
}"""

def dump_unexpected(name: str, data) -> str:
    """Save a response we could not read to data/debug/ (local only), so the parser can be fixed from it
    without making the request again. Returns the file path."""
    return save_debug(name, data)


_JOB_TYPE_WANTED = {"fulltime": "full time", "parttime": "part time", "contract": "contract", "internship": "intern"}


def get(d, *paths):
    """First non-empty value along dotted paths; lists step into their first element."""
    for path in paths:
        cur = d
        for k in path.split("."):
            if isinstance(cur, list):
                cur = cur[0] if cur else None
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, list) and cur and not isinstance(cur[0], (dict, list)):
            cur = cur[0]
        if cur not in (None, "", [], {}):
            return cur
    return None


def job_id_from_url(url: str) -> tuple[str, str] | None:
    """(country, job id) from a JobStreet job link, e.g. https://my.jobstreet.com/job/95667394?ref=..."""
    m = re.search(r"https?://(?:www\.)?([a-z]{2})\.jobstreet\.com/(?:[^\s?#]*/)?job/(\d+)", url) \
        or re.search(r"https?://(?:www\.)?([a-z]{2})\.jobstreet\.com/[^\s]*[?&]jobId=(\d+)", url)
    if not m:
        return None
    country = m.group(1).upper()
    return (country, m.group(2)) if country in SITES else None


def _parse_date(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


class JobStreetSource:
    key = "jobstreet"

    def __init__(self, client: PoliteClient, max_results: int = 50, known_ids: set[str] | None = None,
                 country: str = "MY", now: datetime | None = None):
        self.client = client
        self.max_results = max_results
        self.known_ids = known_ids or set()
        self.host, self.site_key, self.locale, self.tz = SITES[country]
        self.country = country
        self.now = now or datetime.now(UTC)
        self._session = str(uuid.uuid4())  # random per run; not tied to me
        self._details_failed = False  # one non-block GraphQL failure -> no more detail requests this run
        self.notes: list[str] = []
        self.collected: list[NormalizedJob] = []

    # ---------- search ----------

    def search(self, keywords: str, where: str, days: int, page: int = 1, page_size: int = PAGE_SIZE) -> list[dict]:
        params = {"siteKey": self.site_key, "sourcesystem": "houston", "keywords": keywords, "page": page,
                  "pageSize": page_size, "locale": self.locale}
        if where:
            params["where"] = where
        if days:
            params["daterange"] = days
        data = self.client.get_json(f"https://{self.host}/api/jobsearch/v5/search", params=params)
        cards = data.get("data") if isinstance(data, dict) else None
        if not isinstance(cards, list):
            saved = dump_unexpected("jobstreet-search", data)
            raise SchemaChanged(f"JobStreet search: response has no job list ('data'); saved to {saved}")
        self.last_search = data
        return cards

    @staticmethod
    def parse_card(c: dict) -> dict | None:
        jid, title = get(c, "id", "jobId"), get(c, "title")
        if not jid or not title:
            return None
        arrangement = get(c, "workArrangements.data.label.text", "workArrangements.label.text", "workArrangement")
        return {
            "id": str(jid), "title": str(title).strip(),
            "company": get(c, "advertiser.description", "companyName", "advertiser.name") or "",
            "location": get(c, "locations.label", "location", "jobLocation.label", "suburb") or "",
            "work_type": get(c, "workTypes", "workType") or "",
            "arrangement": arrangement_label(arrangement) if arrangement else "",
            "salary": get(c, "salaryLabel", "salary.label", "salary") or "",
            "listed": get(c, "listingDate", "listedAt.dateTimeUtc") or "",
            "teaser": get(c, "teaser") or "",
            "bullets": [b for b in (c.get("bulletPoints") or []) if isinstance(b, str)],
        }

    # ---------- detail ----------

    def detail(self, job_id: str) -> dict:
        """Full job as a dict (title, company, location, description, ...). Raises on failure.

        GraphQL only. The job web page is NOT used: it answered 403 on 13 Nov, and that refusal is respected
        (decision #102). After one non-block failure the rest of the run doesn't ask again (summaries kept)."""
        if self._details_failed:
            raise SourceError("job details unavailable this run")
        try:
            return self._detail_graphql(job_id)
        except RateLimited:
            raise
        except SourceError as e:
            self._details_failed = True
            self.notes.append(f"job details: GraphQL failed ({e}); the rest of this run keeps search summaries")
            raise

    def _detail_graphql(self, job_id: str) -> dict:
        variables = {"jobId": job_id, "jobDetailsViewedCorrelationId": str(uuid.uuid4()), "sessionId": self._session,
                     "zone": "asia-4", "locale": self.locale, "languageCode": "en", "countryCode": self.country,
                     "timezone": self.tz}
        data = self.client.post_json(f"https://{self.host}/graphql",
                                     {"operationName": "jobDetails", "variables": variables, "query": JOB_DETAILS_QUERY})
        job = get(data, "data.jobDetails.job")
        if not isinstance(job, dict) or not get(job, "content"):
            saved = dump_unexpected("jobstreet-detail", data)
            raise SchemaChanged(f"JobStreet job details: no job content in the response; saved to {saved}")
        arrangement = get(job, "workArrangements.arrangements.label", "workArrangements.label")
        return {
            "id": str(get(job, "id") or job_id), "title": get(job, "title") or "",
            "company": get(job, "advertiser.name") or "", "location": get(job, "location.label") or "",
            "work_type": get(job, "workTypes.label") or "",
            "arrangement": arrangement_label(arrangement) if arrangement else "",
            "salary": get(job, "salary.label") or "", "listed": get(job, "listedAt.dateTimeUtc") or "",
            "description": clean_text(get(job, "content") or ""),
        }

    # ---------- the plugin interface ----------

    def to_normalized(self, card: dict, full: dict | None) -> NormalizedJob:
        j = {**card, **{k: v for k, v in (full or {}).items() if v}}
        description = j.get("description") or "\n".join(
            [j.get("teaser", ""), *[f"- {b}" for b in j.get("bullets", [])],
             "", SUMMARY_ONLY]).strip()
        lo, hi, cur = find_salary(j.get("salary", ""))
        listed = _parse_date(j.get("listed"))
        return NormalizedJob(
            title=j["title"], company=j.get("company", ""), location=j.get("location", ""), description=description,
            url=f"https://{self.host}/job/{j['id']}", source=self.key, salary_min=lo, salary_max=hi,
            salary_currency=cur, job_type=normalize_job_type(j.get("work_type", "")) or j.get("work_type", ""),
            work_arrangement=j.get("arrangement", ""), posted_date=listed.date() if listed else None,
            extra={"external_ids": {self.key: j["id"]}},
        )

    def _wanted(self, card: dict, profile) -> bool:
        want = _JOB_TYPE_WANTED.get(getattr(profile, "job_type", "") or "")
        if want and card["work_type"] and want not in card["work_type"].lower():
            return False
        listed = _parse_date(card["listed"])
        days = getattr(profile, "days", 0) or 0
        return not (days and listed and listed < self.now - timedelta(days=days))

    def fetch(self, search_profile) -> list[NormalizedJob]:
        cap = min(self.max_results, getattr(search_profile, "max_results", 0) or self.max_results)
        wheres = [loc for loc in search_profile.locations if loc.strip().lower() != "remote"] or [""]
        # Always ask for a full page (one request either way), so cards removed by the job-type / date
        # filters don't trigger another page. Page 2 only when the cap itself is larger than a page.
        pages = 1 if cap <= PAGE_SIZE else MAX_PAGES_PER_QUERY
        cards: dict[str, dict] = {}
        for kw in search_profile.keywords:
            for where in wheres:
                for page in range(1, pages + 1):
                    if len(cards) >= cap:
                        break
                    raw = self.search(kw, where, search_profile.days, page, PAGE_SIZE)
                    parsed = [p for p in (self.parse_card(c) for c in raw) if p]
                    if raw and not parsed:
                        saved = dump_unexpected("jobstreet-search", getattr(self, "last_search", raw))
                        raise SchemaChanged(f"JobStreet search: job cards have no id/title; saved to {saved}")
                    for p in parsed:
                        # Stored cards are skipped here, not after the cap: they must not use up the run's budget.
                        if (p["id"] not in cards and p["id"] not in self.known_ids and self._wanted(p, search_profile)
                                and len(cards) < cap):
                            cards[p["id"]] = p
                    if len(raw) < PAGE_SIZE:
                        break  # last page
        out = self.collected = []  # kept on the object so a 429 mid-run still saves what was fetched
        pending = [c for c in cards.values() if c["id"] not in self.known_ids]  # stored: never re-fetched
        for i, card in enumerate(pending):
            try:
                full = self.detail(card["id"])
            except RateLimited:
                # Blocked: stop asking, but keep every card already in hand as a "summary only" job.
                rest = pending[i:]
                out.extend(self.to_normalized(c, None) for c in rest)
                self.known_ids.update(c["id"] for c in rest)
                self.notes.append(f"job details blocked: saved {len(rest)} job(s) from their search summary")
                raise
            except SourceError as e:
                if not self._details_failed or "unavailable this run" not in str(e):
                    self.notes.append(f"job {card['id']}: {e}; saved the search summary instead")
                full = None
            out.append(self.to_normalized(card, full))
            self.known_ids.add(card["id"])  # a later search profile in the same run won't fetch it again
        return out
