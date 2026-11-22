"""Create a demo database full of FAKE data (for screenshots and trying the app). Never touches data/jobfinder.db.

    backend\\.venv\\Scripts\\python scripts\\seed_demo.py [target_dir]      (default: demo_data\\)

Everything goes through the app's own API in-process (FastAPI TestClient), so scores, filters and documents are
exactly what the app would produce. No network: the scheduler is off and sources are the offline fakes.
Run the app on it with:  set JOBFINDER_DATA_DIR=demo_data  (see scripts/screenshots.py).
"""
import os
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL_DATA = (ROOT / "data").resolve()


def demo_env(target: Path) -> dict:
    """Environment for anything that runs on the demo data: own folder, no scheduler, offline sources."""
    return {"JOBFINDER_DATA_DIR": str(target), "JOBFINDER_NO_SCHEDULER": "1", "JOBFINDER_FAKE_SOURCES": "1",
            "JOBFINDER_TEMPLATES_DIR": str(target / "prompt-templates")}


def safe_target(arg: str | None) -> Path:
    target = Path(arg or ROOT / "demo_data").resolve()
    if target == REAL_DATA or REAL_DATA in target.parents:
        sys.exit(f"Refusing to write into {target}: that is the real data folder.")
    return target


PROFILE = {
    "name": "Aisyah Tan", "email": "aisyah.tan@example.com", "phone": "012-000 0000", "location": "Petaling Jaya",
    "linkedin_url": "linkedin.com/in/example-aisyah-tan", "github_url": "github.com/example-aisyah",
    "years_of_experience": 0.5, "years_confirmed": True, "education_level": "Degree",
    "education_field": "Software Engineering", "degree_status": "in_progress",
    "expected_graduation": (date.today() + timedelta(days=240)).isoformat(),
    "languages": ["English", "Bahasa Malaysia", "Mandarin"], "preferred_locations": ["Kuala Lumpur", "Selangor"],
    "remote_ok": True, "skills": ["Python", "JavaScript", "SQL", "Git"], "notes": "",
}

BANK = [
    {"type": "work", "title": "Software Engineering Intern", "organization": "Kedai Tech Sdn Bhd", "start": "Jun 2025",
     "end": "Sep 2025", "skills": ["React", "TypeScript", "Python", "FastAPI", "PostgreSQL", "pytest"],
     "bullets": ["Built internal dashboards with React and TypeScript used by 3 operations teams",
                 "Wrote REST APIs in Python (FastAPI) backed by PostgreSQL",
                 "Added automated tests with pytest, raising coverage from 40% to 75%"]},
    {"type": "project", "title": "Campus Food Ordering App", "organization": "Universiti Contoh Malaysia",
     "start": "Jan 2025", "end": "Apr 2025", "skills": ["Flutter", "Firebase", "Scrum"],
     "bullets": ["Flutter mobile app with Firebase authentication, piloted by 200+ students",
                 "Led a team of 4 using two-week Scrum sprints"]},
    {"type": "project", "title": "Bus Arrival Tracker", "organization": "Personal project", "start": "2024", "end": "2024",
     "skills": ["Node.js", "Express", "MongoDB", "Docker"],
     "bullets": ["Real-time bus arrival web app built with Node.js, Express and MongoDB",
                 "Packaged with Docker and deployed on a small cloud VM"]},
    {"type": "education", "title": "Bachelor of Software Engineering (Hons)", "organization": "Universiti Contoh Malaysia",
     "start": "Sep 2023", "end": "Present", "bullets": ["CGPA 3.70"], "skills": []},
    {"type": "certification", "title": "AWS Certified Cloud Practitioner", "organization": "Amazon Web Services",
     "start": "", "end": "2025", "bullets": [], "skills": ["AWS"]},
    {"type": "achievement", "title": "Dean's List (4 semesters)", "organization": "Faculty of Computing",
     "start": "", "end": "2025", "bullets": [], "skills": []},
]

JOBS = [
    ("Junior Software Engineer", "Contoh Fintech Sdn Bhd", "Kuala Lumpur", """About the role
You will build and maintain web services for our payments platform.
Requirements:
- Degree in Computer Science, Software Engineering or related field
- Fresh graduates are welcome
- Good knowledge of Python and SQL
- Experience with React
- Familiar with Git
Nice to have:
- Docker
- AWS
- Good command of English"""),
    ("Graduate Software Developer", "Syarikat Contoh Logistik Bhd", "Shah Alam, Selangor", """Responsibilities
- Develop features for our warehouse management system
Requirements:
- Degree in Software Engineering or IT
- 0-1 years of experience
- Java and Spring Boot
- SQL and Git
Preferred:
- Docker is a plus"""),
    ("Frontend Developer (Fresh Graduate)", "Kedai Digital Contoh Sdn Bhd", "Petaling Jaya, Selangor", """What you need
- Diploma or Degree in Computer Science
- React and TypeScript
- HTML, CSS, Tailwind CSS
- Git
Bonus points
- Figma
- Next.js"""),
    ("Backend Engineer", "Contoh Health Tech Sdn Bhd", "Cyberjaya, Selangor", """Requirements:
- Degree in Computer Science
- At least 1 year of experience
- Python with FastAPI or Django
- PostgreSQL
- Docker and Kubernetes
- English and Bahasa Malaysia"""),
    ("Senior DevOps Engineer", "Contoh Cloud Sdn Bhd", "Kuala Lumpur", """Requirements:
- Minimum 6 years of experience
- Kubernetes, Terraform, AWS
- Lead a team of engineers"""),
    ("QA Engineer", "Contoh Retail Bhd", "Kuala Lumpur", """Requirements:
- Degree in IT
- Selenium and manual testing
- SQL
- Mandarin is required to liaise with regional teams"""),
    ("Software Engineer (Graduate Programme)", "Contoh Software Sdn Bhd", "Petaling Jaya, Selangor", """Requirements:
- Degree in Software Engineering or Computer Science, fresh graduates welcome
- Python or JavaScript
- React
- SQL and Git
Good to have:
- AWS"""),
]

TRACKER = [  # job index -> statuses walked through, days ago applied
    (0, ["Applied", "Interview"], 9), (1, ["Applied"], 4), (2, [], None), (3, ["Applied", "Rejected"], 20), (5, ["Applied"], 2),
]


def demo_run_log() -> None:
    """A short, fake automation history (no fetching happens), so the Automations run log has something to show."""
    from sqlmodel import Session

    from app.db import engine
    from models import AutomationRun
    from models._base import utcnow

    def detail(source, profiles, cap, fetched, new, merged, hidden, requests, notes=(), status="ok", error=""):
        return {"source": source, "status": status, "profiles": profiles, "cap": cap, "fetched": fetched, "new": new,
                "merged": merged, "hidden": hidden, "requests": requests, "notes": list(notes), "error": error}

    now = utcnow().replace(second=0, microsecond=0)
    daily = ["KL/Selangor software"]
    runs = [
        (now - timedelta(days=9, hours=2), "fetch_jobs", "schedule", "ok", [
            detail("jobstreet", daily, 50, 18, 9, 6, 3, 21),
            detail("linkedin", daily, 25, 12, 4, 7, 1, 9, ["JobSpy warning: job_type fulltime isn't supported, ignoring it"]),
            detail("indeed", daily, 25, 0, 0, 0, 0, 2, status="error", error="HTTP 429 (too many requests)")]),
        (now - timedelta(days=9, hours=2) + timedelta(minutes=1), "score_new_jobs", "chain", "ok", "scored 13 new jobs"),
        (now - timedelta(days=2, hours=1), "fetch_jobs", "manual", "ok", [
            detail("jobstreet", ["Smoke test"], 5, 5, 2, 3, 0, 7),
            detail("linkedin", ["Smoke test"], 5, 5, 1, 4, 0, 4, ["JobSpy warning: location 'Bangsar South' not found, searching the country"]),
            detail("glassdoor", [], None, 0, 0, 0, 0, 0, status="skipped", error="no enabled search profile uses this source")]),
        (now - timedelta(days=1, hours=3), "follow_up_reminder", "schedule", "ok", "1 follow-up due today"),
    ]
    with Session(engine) as session:
        for at, key, trigger, result, body in runs:
            details = body if isinstance(body, list) else []
            message = body if isinstance(body, str) else ""
            session.add(AutomationRun(automation_key=key, trigger=trigger, started_at=at, finished_at=at + timedelta(minutes=1),
                                      result=result, items_processed=sum(d["new"] for d in details) or (13 if key == "score_new_jobs" else 0),
                                      message=message, details=details))
        session.commit()


def seed(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    os.environ.update(demo_env(target))
    sys.path.insert(0, str(ROOT / "backend"))
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, base_url="http://127.0.0.1") as c:
        def ok(r):
            assert r.status_code < 300, r.text
            return r.json()

        ok(c.post("/api/resumes/import", json={"name": "Software Dev", "items": BANK, "profile": {}}))
        ok(c.put("/api/profile", json=PROFILE))
        ids = [ok(c.post("/api/jobs/manual", json={"title": t, "company": co, "location": loc, "description": jd}))["id"]
               for t, co, loc, jd in JOBS]
        for idx, statuses, days in TRACKER:
            app_id = ok(c.post("/api/applications", json={"job_id": ids[idx]}))["id"]
            for st in statuses:
                body = {"status": st}
                if st == "Applied":
                    body["applied_at"] = (date.today() - timedelta(days=days)).isoformat()
                ok(c.patch(f"/api/applications/{app_id}", json=body))
        # a saved resume version and a template cover letter for the first job (no AI needed)
        resume = ok(c.post("/api/documents/resume", json={
            "job_id": ids[0], "source": "manual",
            "summary": "Final-year Software Engineering student with internship experience building React dashboards "
                       "and Python REST APIs.",
            "skills": ["Python", "SQL", "React", "TypeScript", "Git", "Docker", "AWS"],
            "sections": [{"section": "Experience", "items": [
                {"source_id": "B1", "text": "Wrote REST APIs in Python (FastAPI) backed by PostgreSQL"},
                {"source_id": "B1", "text": "Built internal dashboards with React and TypeScript used by 3 operations teams"},
                {"source_id": "B1", "text": "Added automated tests with pytest, raising coverage from 40% to 75%"}]},
                {"section": "Projects", "items": [
                    {"source_id": "B3", "text": "Real-time bus arrival web app built with Node.js, Express and MongoDB"},
                    {"source_id": "B3", "text": "Packaged with Docker and deployed on a small cloud VM"},
                    {"source_id": "B2", "text": "Flutter mobile app with Firebase authentication, piloted by 200+ students"}]}],
            "add_original_ids": ["B4", "B5", "B6"]}))
        draft = ok(c.post("/api/documents/cover-letter/template-draft", json={"job_id": ids[0]}))
        letter = ok(c.post("/api/documents/cover-letter", json={**draft, "job_id": ids[0], "source": "template"}))
        first_app = next(a for a in ok(c.get("/api/applications")) if a["job_id"] == ids[0])
        ok(c.patch(f"/api/applications/{first_app['id']}", json={"resume_version_id": resume["id"],
                                                                  "cover_letter_version_id": letter["id"]}))
        ok(c.post("/api/automations/high_match_alert/run"))
        # a second base resume (education, the internship and the AWS certificate), for the Resume page
        bank = {i["code"]: i["id"] for i in ok(c.get("/api/experience"))}
        ok(c.post("/api/resumes", json={"name": "IT support", "item_ids": [bank[k] for k in ("B1", "B4", "B5") if k in bank]}))
        demo_run_log()
        print(f"Demo data in {target}: {len(ids)} jobs, {len(TRACKER)} tracker cards, resume version {resume['version']}.")


if __name__ == "__main__":
    seed(safe_target(sys.argv[1] if len(sys.argv) > 1 else None))
