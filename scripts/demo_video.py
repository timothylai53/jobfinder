"""Record the README demo (FAKE demo data, offline) and turn it into docs/demo.gif (+ docs/demo.mp4).

    backend\\.venv\\Scripts\\python scripts\\demo_video.py

Flow (about 25 s): Today -> a job's score and verdict -> score details -> Copy-Paste tailor review with red and
amber flags -> the resume as it prints (PDF layout preview).
Uses scripts/screenshots.py's demo servers (ports 8731/5731, demo_data/, every non-local request blocked).
Needs ffmpeg on PATH for the GIF/MP4 conversion (a local tool, not a project dependency).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from screenshots import FABRICATED_REPLY, ROOT, run_on_demo  # noqa: E402

OUT = ROOT / "docs"
SIZE = {"width": 1280, "height": 760}


def record(base: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="jobfinder-demo-"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=SIZE, record_video_dir=str(tmp), record_video_size=SIZE)
        ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(("http://127.0.0.1", "http://localhost", "data:"))
                  else r.abort())  # offline: nothing leaves this laptop
        page = ctx.new_page()
        pause = page.wait_for_timeout

        page.goto(base + "/")
        page.wait_for_load_state("networkidle")
        pause(2600)  # Today: next steps, stats

        jobs = page.request.get(f"{base}/api/jobs").json()
        saved = next(j for j in jobs if j["title"].startswith("Frontend Developer"))
        page.get_by_role("link", name="Tailor resume: No resume yet for Frontend Developer", exact=False).click()
        page.wait_for_url(f"**/jobs/{saved['id']}")
        page.wait_for_load_state("networkidle")
        pause(3000)  # big score, one-sentence verdict, what's missing

        page.get_by_role("tab", name="Score details").click()
        pause(2600)  # every point explained

        page.locator("header").get_by_role("button", name="Tailor resume").click()
        page.get_by_placeholder("Paste the chat's reply here", exact=False).fill(FABRICATED_REPLY)
        pause(900)
        page.get_by_role("button", name="Check reply").click()
        page.get_by_text("flagged in red", exact=False).first.wait_for()
        pause(2600)  # red / amber summary, summary and skills flags
        page.get_by_role("heading", name="Experience").first.scroll_into_view_if_needed()
        page.mouse.wheel(0, 240)
        pause(3200)  # side by side: amber "Docker isn't in B1", red B99 that can't be saved
        page.keyboard.press("Escape")

        docs = page.request.get(f"{base}/api/jobs").json()
        first = next(j for j in docs if j["title"] == "Junior Software Engineer")
        resume = next(d for d in page.request.get(f"{base}/api/jobs/{first['id']}/documents").json() if d["type"] == "resume")
        page.goto(f"{base}/api/documents/{resume['id']}/html")
        page.add_style_tag(content="html { background: #e9edf1 } body { background: white; max-width: 820px; "
                                   "margin: 24px auto; padding: 40px 48px; box-shadow: 0 6px 30px -12px rgb(0 0 0 / .25) }")
        pause(3200)  # the ATS-friendly resume, as it prints to PDF

        video = page.video.path()
        ctx.close()
        browser.close()
    return Path(video)


def convert(webm: Path) -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not installed: winget install Gyan.FFmpeg (then run this again).")
    OUT.mkdir(exist_ok=True)
    trim = ["-ss", "0.6"]  # skip the blank first frames before the page paints
    gif = OUT / "demo.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *trim, "-i", str(webm), "-vf",
                    "fps=10,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
                    "-loop", "0", str(gif)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *trim, "-i", str(webm), "-vf", "scale=1280:-2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "slow", "-movflags", "+faststart",
                    "-an", str(OUT / "demo.mp4")], check=True)
    for f in (gif, OUT / "demo.mp4"):
        print(f"{f.name}: {f.stat().st_size / 1_000_000:.1f} MB")


def main() -> None:
    holder: dict[str, Path] = {}
    run_on_demo(lambda base: holder.setdefault("video", record(base)))
    convert(holder["video"])


if __name__ == "__main__":
    main()
