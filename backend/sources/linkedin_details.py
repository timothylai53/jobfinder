"""LinkedIn job descriptions, fetched by us (not by JobSpy) so every request is paced and every block is seen.

JobSpy's LinkedIn scraper fetches each job page back-to-back with no delay and only logs a 403/429 there,
so it is called with fetch_description=False (search pages only) and this module reads each NEW job's
public, logged-out page through PoliteClient: 2-6 s apart, 403/429/999 -> RateLimited -> 24 h pause.
A redirect away from /jobs/view/ (e.g. to the login wall) is LinkedIn refusing us: also treated as rate-limited.
"""
from bs4 import BeautifulSoup

from sources.http import PoliteClient, RateLimited, SchemaChanged, save_debug, save_response
from sources.manual import clean_text

BASE = "https://www.linkedin.com"


def job_id_of(url: str, fallback: str = "") -> str:
    import re
    m = re.search(r"/jobs/view/(?:[^/?#]*-)?(\d+)", url or "")
    return m.group(1) if m else fallback


def fetch_description(client: PoliteClient, job_id: str) -> dict:
    """{'description': ..., 'job_type': ..., 'seniority': ...} from the public job page."""
    r = client.request("GET", f"{BASE}/jobs/view/{job_id}", headers={"Accept": "text/html"})
    if not r.url.path.startswith("/jobs/view/"):
        # sent to /authwall or a login page: LinkedIn wants us to stop
        raise RateLimited(429, str(r.url), save_response(r, "redirected away from the job page"))
    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.find("div", class_="show-more-less-html__markup")
    if body is None:
        saved = save_debug("linkedin-job-page", r.text[:200_000])
        raise SchemaChanged(f"LinkedIn job page has no description block; saved to {saved}")

    def criterion(name: str) -> str:
        for h in soup.find_all("h3", class_="description__job-criteria-subheader"):
            if h.get_text(strip=True).lower() == name.lower():
                v = h.find_next_sibling("span")
                return v.get_text(strip=True) if v else ""
        return ""

    return {"description": clean_text(str(body)), "job_type": criterion("Employment type"),
            "seniority": criterion("Seniority level")}
