"""Manual import: pasted JD text, or a best-effort fetch of a public job URL."""
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.config import USER_AGENT
from sources.base import NormalizedJob


class FetchError(Exception):
    pass


def clean_text(html_or_text: str) -> str:
    soup = BeautifulSoup(html_or_text, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for blk in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "ul", "ol", "tr"]):
        blk.insert_after("\n")
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in soup.get_text().splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def _find_jobposting(data):
    if isinstance(data, list):
        for d in data:
            r = _find_jobposting(d)
            if r:
                return r
    elif isinstance(data, dict):
        t = data.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            return data
        if "@graph" in data:
            return _find_jobposting(data["@graph"])
    return None


def _location_from_ld(jp: dict) -> str:
    if str(jp.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        return "Remote"
    loc = jp.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
            parts = [p if isinstance(p, str) else (p or {}).get("name") for p in parts]
            return ", ".join(p for p in parts if p)
    return ""


def _num(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _from_jobposting(jp: dict, url: str) -> NormalizedJob:
    org = jp.get("hiringOrganization") or {}
    sal = jp.get("baseSalary") if isinstance(jp.get("baseSalary"), dict) else {}
    val = sal.get("value") if isinstance(sal.get("value"), dict) else {}
    etype = jp.get("employmentType") or ""
    return NormalizedJob(
        title=str(jp.get("title") or "").strip(),
        company=(org.get("name") if isinstance(org, dict) else str(org)) or "",
        location=_location_from_ld(jp),
        description=clean_text(jp.get("description") or ""),
        url=url,
        salary_min=_num(val.get("minValue") or val.get("value")),
        salary_max=_num(val.get("maxValue")),
        salary_currency=sal.get("currency") or "",
        job_type=", ".join(etype) if isinstance(etype, list) else str(etype),
    )


def extract_from_html(html: str, url: str = "") -> NormalizedJob:
    soup = BeautifulSoup(html, "html.parser")
    # 1. schema.org JobPosting (most job boards embed this for search engines)
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            jp = _find_jobposting(json.loads(tag.string or ""))
        except (json.JSONDecodeError, TypeError):
            continue
        if jp:
            return _from_jobposting(jp, url)

    # 2. generic page: h1 / og:title + main/article text
    def meta(name: str) -> str:
        m = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        return (m.get("content") or "").strip() if m else ""

    title = (soup.h1.get_text(strip=True) if soup.h1 else "") or meta("og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    company = meta("og:site_name")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "form"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return NormalizedJob(title=title, company=company, description=clean_text(str(main)), url=url)


MAX_REDIRECTS = 5


def check_public_url(url: str) -> None:
    """SSRF guard: only http(s) URLs whose host resolves to public internet addresses. Refuses this machine
    (127.0.0.1, localhost, Ollama's port), the home network (192.168.x.x, 10.x.x.x) and link-local/cloud metadata
    addresses (169.254.x.x). Called before the first request and again on every redirect."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("URL must start with http:// or https://")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError) as e:
        raise FetchError(f"Could not find the site {parts.hostname!r}. Paste the JD text instead.") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise FetchError("That address is on this computer or a private network, so it is not fetched. "
                             "Paste the JD text instead.")


def fetch_url(url: str, timeout: float = 15.0) -> NormalizedJob:
    """One polite, logged-out GET of a public page. Raises FetchError with a readable message.
    Redirects are followed by hand (at most 5) so each new address is checked too."""
    url = url.strip()
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=timeout,
                          follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                check_public_url(url)
                r = client.get(url)
                if not r.is_redirect:
                    break
                url = urljoin(url, r.headers.get("location", ""))
            else:
                raise FetchError("Too many redirects. Paste the JD text instead.")
    except httpx.HTTPError as e:
        raise FetchError(f"Could not fetch the page ({e.__class__.__name__}). Paste the JD text instead.") from e
    if r.status_code >= 400:
        raise FetchError(f"The site answered HTTP {r.status_code}. Paste the JD text instead.")
    job = extract_from_html(r.text, str(r.url))
    if len(job.description) < 200:
        raise FetchError("The page loaded but no job description was found (it may need JavaScript or a login). "
                         "Paste the JD text instead.")
    return job
