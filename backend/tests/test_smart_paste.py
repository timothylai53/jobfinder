"""Smart paste: whole copied job pages (fake, modelled on JobStreet / LinkedIn layouts) -> job drafts."""
import re
from pathlib import Path

from app.settings_store import default_location_map
from sources.smart_paste import extract, find_salary, is_noise

PAGES = Path(__file__).parent / "fixtures" / "pages"
MAP = default_location_map()


def page(name: str) -> str:
    return (PAGES / name).read_text(encoding="utf-8")


REAL = Path(__file__).parent / "fixtures" / "jobstreet_real_1.txt"
REAL_JD_START = "Responsibilities"
REAL_JD_END = "Fresh graduates are encouraged to apply."


def real_paste() -> str:
    return REAL.read_text(encoding="utf-8")


def plain_variant(md: str) -> str:
    """The same page as a browser puts it in a textarea: no Markdown links, plus the logo alt text."""
    text = re.sub(r"\[([^\]]*)\]\((https?://[^)\s]*)\)", r"\1", md)
    return text.replace("Junior Software Engineer\n", "Contoh Insurans (Malaysia) Berhad logo\nJunior Software Engineer\n", 1)


def check_real(d):
    assert d.source == "jobstreet"
    assert d.title == "Junior Software Engineer"
    assert d.company == "Contoh Insurans (Malaysia) Berhad"
    assert d.location == "Kuala Lumpur City Centre, Kuala Lumpur"
    assert d.work_arrangement == "Hybrid"
    assert d.job_type == "Full time"
    assert (d.salary_min, d.salary_max) == (None, None) and d.salary_undisclosed  # "Salary undisclosed"
    assert d.uncertain == []
    assert d.description.startswith(REAL_JD_START)
    assert d.description.endswith(REAL_JD_END)
    for noise in ("High application volume", "Posted 4d ago", "Employer questions", "Company profile",
                  "Contoh General Insurance", "Report this job advert", "People search", "Job seekers"):
        assert noise not in d.description, noise
    assert "- Must be proficient in at least one (1) programming language. (C#/ Java/ Javascript or equivalent)" in d.description


def test_jobstreet_real_paste():
    d = extract(real_paste(), MAP)
    check_real(d)
    assert d.url == "https://my.jobstreet.com/job/95667394"  # built from the jobId in the page's own links


def test_jobstreet_real_paste_plain_text_with_logo_line():
    d = extract(plain_variant(real_paste()), MAP)
    check_real(d)
    assert d.url == ""  # no URL in a plain-text paste -> leave the field empty


def test_jobstreet_fake_layout():
    d = extract(page("jobstreet_copy.txt"), MAP)
    assert d.title == "Junior Software Engineer"
    assert d.company == "Kedai Tech Sdn Bhd"
    assert d.location == "Cyberjaya, Selangor"
    assert (d.salary_min, d.salary_max, d.salary_currency) == (3800, 4800, "MYR")
    assert d.job_type == "Full time"
    assert set(d.detected) == {"title", "company", "location", "salary", "job_type"}
    assert d.source == "jobstreet" and d.uncertain == []
    # description keeps the JD, drops nav, employer questions, warnings, similar jobs and footer
    assert d.description.startswith("About the role")
    assert "Build REST APIs with Python and Django" in d.description
    assert "Good command of English and Bahasa Malaysia" in d.description
    for noise in ("Skip to content", "Quick apply", "Employer questions", "Report this job advert",
                  "Similar jobs", "Graduate Developer", "© 2026 SEEK", "Career advice"):
        assert noise not in d.description, noise
    assert d.removed_lines > 20


def test_linkedin_page():
    d = extract(page("linkedin_copy.txt"), MAP)
    assert d.title == "Junior Frontend Developer"
    assert d.company == "Contoh Labs"
    assert d.location == "Kuala Lumpur, Federal Territory of Kuala Lumpur, Malaysia"
    assert d.work_arrangement == "Hybrid"
    assert d.job_type == "Full time"
    # generic recognizer: every header field is shown as "please check"
    assert d.source == "generic" and {"title", "company", "location"} <= set(d.uncertain)
    assert d.salary_min is None
    assert d.description.startswith("Contoh Labs builds payment apps")
    assert "Proficient in JavaScript, HTML and CSS" in d.description
    for noise in ("Show more", "Seniority level", "Referrals increase", "People also viewed", "Another Company",
                  "LinkedIn Corporation", "87 applicants", "Join now"):
        assert noise not in d.description, noise


def test_plain_jd_paste_still_works():
    text = "Graduate Data Analyst\nContoh Analytics Sdn Bhd\nPenang\n\nRequirements\n- SQL and Python\n- Power BI is a plus"
    d = extract(text, MAP)
    assert (d.title, d.company, d.location) == ("Graduate Data Analyst", "Contoh Analytics Sdn Bhd", "Penang")
    assert d.description == "Requirements\n- SQL and Python\n- Power BI is a plus"


def test_body_only_paste_detects_nothing_but_keeps_text():
    text = "Requirements\n- Java\n- Spring Boot\nSalary: RM 4k - 5k per month"
    d = extract(text, MAP)
    assert d.title in ("", "Requirements") or d.description
    assert "Spring Boot" in d.description
    assert (d.salary_min, d.salary_max) == (4000, 5000)


def test_generic_never_uses_navigation_or_logo_lines():
    text = ("Skip to content\nJob search\nPeople search\nCareer advice\nCompanies\nT\nEmployer site\n"
            "Contoh Labs logo\nGraduate QA Engineer\nContoh Labs Sdn Bhd\nPenang\nPosted 2d ago\n"
            "Requirements\n- Selenium")
    d = extract(text, MAP)
    assert d.title == "Graduate QA Engineer"
    assert d.company == "Contoh Labs Sdn Bhd"
    assert d.location == "Penang"
    for nav in ("People search", "Companies", "Employer site", "Contoh Labs logo", "T"):
        assert nav not in (d.title, d.company, d.location)


def test_url_only_from_real_links():
    assert extract("Graduate Developer\nRequirements\n- Python", MAP).url == ""
    li = "Dev\nhttps://www.linkedin.com/jobs/view/junior-dev-at-contoh-4012345678?trk=x\nRequirements\n- Go"
    assert extract(li, MAP).url == "https://www.linkedin.com/jobs/view/4012345678/"
    assert extract("https://careers.example.com/jobs/123", MAP).url == "https://careers.example.com/jobs/123"
    # an unrelated link in a JD is not the job URL
    assert extract("Dev\nRequirements\n- see https://example.com/benefits", MAP).url == ""


def test_salary_formats():
    assert find_salary("RM 3,500 - RM 4,500 per month") == (3500, 4500, "MYR")
    assert find_salary("MYR 5000 to 6500") == (5000, 6500, "MYR")
    assert find_salary("RM4k-6k") == (4000, 6000, "MYR")
    assert find_salary("RM 4,200 monthly") == (4200, None, "MYR")
    assert find_salary("Earn RM 5 vouchers") == (None, None, "")
    assert find_salary("no salary here") == (None, None, "")


def test_noise_lines():
    for line in ("Skip to main content", "Quick apply", "Posted 3d ago", "2 days ago", "87 applicants",
                 "Over 100 applicants", "Show more", "LinkedIn", "JobStreet", "People search", "Companies",
                 "Acme Sdn Bhd logo", "T", "2.7", "High application volume"):
        assert is_noise(line), line
    for line in ("Requirements", "Python", "Remote", "Hybrid", "Build REST APIs"):
        assert not is_noise(line), line


def test_parse_paste_api(client):
    r = client.post("/api/jobs/parse-paste", json={"text": page("jobstreet_copy.txt")})
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "Junior Software Engineer" and d["location"] == "Cyberjaya, Selangor"
    r = client.post("/api/jobs/parse-paste", json={"text": real_paste()}).json()
    assert (r["company"], r["work_arrangement"], r["uncertain"], r["source"]) == (
        "Contoh Insurans (Malaysia) Berhad", "Hybrid", [], "jobstreet")
    assert client.post("/api/jobs/parse-paste", json={"text": "  "}).status_code == 422


def test_real_jobstreet_jd_scoring():
    """Scoring on the real pasted job: years parse, fresh-grad override, slash-separated skills."""
    from matcher.jd_sections import split_clauses
    from matcher.rules import extract_years
    from matcher.scoring import Candidate, score_job
    from skills.matcher import SkillMatcher
    from skills.service import load_seed

    d = extract(real_paste(), MAP)
    clauses = split_clauses(d.description)
    minimum = next(c for c in clauses if c.text.startswith("Minimum two (2) years"))
    assert extract_years([minimum]).years == 2
    years = extract_years(clauses)
    assert years.years == 0 and years.fresh_grad_ok  # "Fresh graduates are encouraged to apply" (decision #11)

    me = Candidate(education_level="Degree", education_field="Software Engineering", preferred_locations=["Kuala Lumpur"],
                   location_map=MAP, skill_evidence={"Java": ["B1"], "SQL": ["profile"]})
    r = score_job(d.description, d.location, me, SkillMatcher(load_seed()))
    assert {"C#", "Java", "JavaScript", "SQL", "MySQL", "Microsoft SQL Server"} <= set(r["required_skills"])
    cats = {c["key"]: c for c in r["categories"]}
    assert cats["years"]["status"] == "met" and not r["gates"]
    edu_field = next(i for i in cats["education"]["items"] if i["name"].startswith("Field"))
    assert edu_field["name"] == "Field: computer science, information technology, software engineering (or related)"
    loc = next(i for i in cats["language_location"]["items"] if i["name"].startswith("Location"))
    assert loc["status"] == "met"
