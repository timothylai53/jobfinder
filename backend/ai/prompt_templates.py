"""Prompt templates, stored as files (brief §6.6): an edited template lives at backend/ai/templates/<name>.md;
without one, the shipped default in backend/ai/templates/defaults/ is used. "Reset" deletes the edited file.
JOBFINDER_TEMPLATES_DIR moves the editable folder (tests use a temporary one)."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent / "templates"
DEFAULTS = HERE / "defaults"
NAMES = ("parse_resume", "deep_analysis", "tailor_resume", "cover_letter", "interview_prep", "fixup")

# Sections every prompt must contain. A template that lost a placeholder gets that section appended, so the
# rules and the output format can never be edited out by accident.
REQUIRED = {
    "parse_resume": ("rules", "resume_text", "schema"),
    "fixup": ("problems", "previous", "schema"),
}
REQUIRED_DEFAULT = ("rules", "profile", "bank", "job", "schema")


def editable_dir() -> Path:
    return Path(os.environ.get("JOBFINDER_TEMPLATES_DIR") or HERE)


def _check(name: str) -> None:
    if name not in NAMES:
        raise KeyError(f"unknown template {name!r}")


def default_text(name: str) -> str:
    _check(name)
    return (DEFAULTS / f"{name}.md").read_text(encoding="utf-8")


def load(name: str) -> str:
    _check(name)
    f = editable_dir() / f"{name}.md"
    return f.read_text(encoding="utf-8") if f.exists() else default_text(name)


def is_edited(name: str) -> bool:
    _check(name)
    return (editable_dir() / f"{name}.md").exists()


def save(name: str, text: str) -> None:
    _check(name)
    d = editable_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(text.replace("\r\n", "\n"), encoding="utf-8")


def reset(name: str) -> None:
    _check(name)
    (editable_dir() / f"{name}.md").unlink(missing_ok=True)


def required_placeholders(name: str) -> tuple[str, ...]:
    return REQUIRED.get(name, REQUIRED_DEFAULT)


def render(name: str, values: dict[str, str]) -> str:
    """Fill {{placeholders}}; append any required section the template lost."""
    text = load(name)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    missing = [k for k in required_placeholders(name) if "{{" + k + "}}" not in load(name)]
    for k in missing:
        text += f"\n\n## {k.replace('_', ' ').capitalize()}\n{values.get(k, '')}"
    return text.strip() + "\n"
