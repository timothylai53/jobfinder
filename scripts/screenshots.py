"""Take the README screenshots from FAKE demo data. Offline: every request that isn't to this laptop is blocked.

    backend\\.venv\\Scripts\\python scripts\\screenshots.py

1. Seeds demo_data\\ (scripts/seed_demo.py; never data\\jobfinder.db).
2. Starts the backend (port 8731) and the Vite dev server (port 5731) on it, so a running JobFinder on
   8730/5730 is left alone.
3. Saves PNGs to docs/screenshots/, then stops both servers.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from seed_demo import demo_env, safe_target  # noqa: E402

API, UI = 8731, 5731
OUT = ROOT / "docs" / "screenshots"
PY = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# A pasted chat reply with problems the fabrication guard must catch (IDs refer to the demo bank).
FABRICATED_REPLY = """```json
{
  "summary": "Software engineer with Kubernetes experience who cut costs by 60%.",
  "skills_order": ["Python", "React", "Kubernetes"],
  "sections": [
    {"section": "Experience", "items": [
      {"source_id": "B1", "text": "Wrote REST APIs in Python (FastAPI) backed by PostgreSQL"},
      {"source_id": "B1", "text": "Containerised the dashboards with Docker"},
      {"source_id": "B99", "text": "Led a team of 8 engineers at a bank"},
      {"source_id": "", "text": "Deployed microservices to Kubernetes"}
    ]},
    {"section": "Projects", "items": [
      {"source_id": "B3", "text": "Real-time bus arrival web app built with Node.js, Express and MongoDB"}
    ]}
  ],
  "omitted_ids": [],
  "notes": "Kubernetes is asked for but not in the bank."
}
```"""


def wait(url: str, seconds: int = 60) -> None:
    for _ in range(seconds * 2):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not start")


def run_on_demo(action) -> None:
    """Seed demo_data, start the backend and Vite on the demo ports, run `action(base_url)`, always stop both."""
    target = safe_target(None)
    subprocess.run([str(PY), str(ROOT / "scripts" / "seed_demo.py"), str(target)], check=True)
    env = {**os.environ, **demo_env(target), "JOBFINDER_API": f"http://127.0.0.1:{API}",
           "JOBFINDER_FRONTEND_ORIGINS": f"http://127.0.0.1:{UI},http://localhost:{UI}"}
    procs = [
        subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(API)],
                         cwd=ROOT / "backend", env=env),
        subprocess.Popen(f"npx vite --host 127.0.0.1 --port {UI} --strictPort", cwd=ROOT / "frontend", env=env, shell=True),
    ]
    try:
        wait(f"http://127.0.0.1:{API}/api/health")
        wait(f"http://127.0.0.1:{UI}/")
        action(f"http://127.0.0.1:{UI}")
    finally:
        for p in procs:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            else:
                p.terminate()


def shoot(base: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("http://127.0.0.1", "http://localhost"))
                   or r.request.url.startswith("data:") else r.abort())  # offline: nothing leaves this laptop
        api = page.request
        jobs = api.get(f"{base}/api/jobs").json()
        jobs = jobs.get("items", jobs) if isinstance(jobs, dict) else jobs
        first = next(j for j in jobs if j["title"] == "Junior Software Engineer")

        def snap(name: str, path: str, full: bool = False) -> None:
            page.goto(base + path)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)

        snap("dashboard", "/")
        snap("jobs", "/jobs")
        saved = next(j for j in jobs if j["title"].startswith("Frontend Developer"))  # saved, no resume yet: "Tailor resume"
        snap("job-detail-score", f"/jobs/{saved['id']}")
        page.set_viewport_size({"width": 1780, "height": 600})
        snap("tracker-kanban", "/tracker")
        page.set_viewport_size({"width": 1440, "height": 900})

        # AI review: open Tailor resume, paste the fabricated reply, check it
        page.goto(f"{base}/jobs/{first['id']}")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="More").click()  # this job is past "Tailor", so it lives in the More menu
        page.get_by_role("button", name="Tailor resume (new version)").click()
        page.get_by_role("button", name="Build prompt").click()  # Start from: the whole bank
        page.get_by_placeholder("Paste the chat's reply here", exact=False).fill(FABRICATED_REPLY)
        page.get_by_role("button", name="Check reply").click()
        page.get_by_text("flagged in red", exact=False).first.wait_for()
        page.get_by_role("heading", name="Summary").first.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / "ai-review-flags.png"))

        # Base resume editor: IT support open, grouped bank items with select-all per group
        page.set_viewport_size({"width": 1180, "height": 900})
        page.goto(f"{base}/resume")
        page.wait_for_load_state("networkidle")
        section = page.locator("section[aria-labelledby=base-resumes]")
        page.get_by_role("button", name="Edit IT support").click()
        page.get_by_role("checkbox", name="Select all in Projects").check()
        section.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        section.screenshot(path=str(OUT / "base-resume-editor.png"))

        # Run log: one aligned row per source, with LinkedIn's warning open in plain words
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto(f"{base}/automations")
        page.wait_for_load_state("networkidle")
        log = page.locator("section[aria-labelledby=run-log]")
        log.get_by_role("row").filter(has_text="LinkedIn").first.get_by_role("button", name="Details").click()
        log.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        log.screenshot(path=str(OUT / "run-log.png"))

        docs = api.get(f"{base}/api/jobs/{first['id']}/documents").json()
        resume = next(d for d in docs if d["type"] == "resume")
        page.set_viewport_size({"width": 860, "height": 800})
        page.goto(f"{base}/api/documents/{resume['id']}/html")
        page.add_style_tag(content="body { padding: 40px 48px; }")  # the PDF's page margins, for the screen
        page.screenshot(path=str(OUT / "resume-preview.png"), full_page=True)
        browser.close()
    print(f"Screenshots in {OUT}")


def main() -> None:
    run_on_demo(shoot)


if __name__ == "__main__":
    main()
