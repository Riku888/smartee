"""Write rendered notes into an Obsidian vault directory.

Local filesystem only (ARCHITECTURE §13.2, adapter #1). The Course Overview
is a generated file: `write_course_overview` overwrites it in place. No
other note is touched.
"""

from datetime import datetime
from pathlib import Path

from smartee.course.bundle import CourseBundle
from smartee.obsidian.naming import course_stem, safe_stem
from smartee.obsidian.render import (
    render_course_overview,
    render_study_note,
    render_today,
)
from smartee.planner import RankedAssignment
from smartee.teacher import StudyNote

_COURSES_DIR = "01 Courses"
_ASSIGNMENTS_DIR = "02 Assignments"
_DASHBOARD_DIR = "00 Dashboard"
_LEGACY_OVERVIEW_FILENAME = "Course Overview.md"


def course_folder_name(bundle: CourseBundle) -> str:
    """Filesystem-safe folder name for a course."""
    return course_stem(bundle.course_label, bundle.course_id)


def course_overview_path(bundle: CourseBundle, vault_dir: Path) -> Path:
    """`01 Courses/<course>/<course>.md` — the folder-note pattern, so the
    file tab and graph node read as the course name, not "Course Overview"."""
    folder = course_folder_name(bundle)
    return Path(vault_dir) / _COURSES_DIR / folder / f"{folder}.md"


def write_course_overview(bundle: CourseBundle, vault_dir: Path) -> Path:
    """Render and write the course's overview note, creating parent folders.
    Removes a stale `Course Overview.md` left by an earlier version.
    Returns the written path."""
    path = course_overview_path(bundle, vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_course_overview(bundle), encoding="utf-8")
    legacy = path.parent / _LEGACY_OVERVIEW_FILENAME
    if legacy.exists() and legacy != path:
        legacy.unlink()
    return path


def study_note_path(note: StudyNote, vault_dir: Path) -> Path:
    filename = safe_stem(note.title, fallback=note.assignment_id) + ".md"
    return Path(vault_dir) / _ASSIGNMENTS_DIR / filename


def write_study_note(note: StudyNote, vault_dir: Path) -> Path:
    """Render and write an AI-generated study note to `02 Assignments/`,
    creating the folder. Overwrites in place. Returns the written path."""
    path = study_note_path(note, vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_study_note(note), encoding="utf-8")
    return path


def today_path(vault_dir: Path) -> Path:
    return Path(vault_dir) / _DASHBOARD_DIR / "Today.md"


def write_today(
    ranked: list[RankedAssignment],
    vault_dir: Path,
    generated_at: datetime | None = None,
) -> Path:
    """Render and write the cross-course `00 Dashboard/Today.md` priority
    note, creating the folder. Overwrites in place. Returns the written path."""
    path = today_path(vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_today(ranked, generated_at), encoding="utf-8")
    return path
