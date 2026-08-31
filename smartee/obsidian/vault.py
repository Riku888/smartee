"""Write rendered notes into an Obsidian vault directory.

Local filesystem only (ARCHITECTURE §13.2, adapter #1). The Course Overview
is a generated file: `write_course_overview` overwrites it in place. No
other note is touched.
"""

import re
from pathlib import Path

from smartee.course.bundle import CourseBundle
from smartee.obsidian.render import render_course_overview, render_study_note
from smartee.teacher import StudyNote

_COURSES_DIR = "01 Courses"
_ASSIGNMENTS_DIR = "02 Assignments"
_OVERVIEW_FILENAME = "Course Overview.md"
_UNSAFE = re.compile(r"[^A-Za-z0-9 _-]+")


def _safe_name(text: str, *, fallback: str) -> str:
    cleaned = " ".join(_UNSAFE.sub(" ", text).split())
    return cleaned or fallback


def course_folder_name(bundle: CourseBundle) -> str:
    """Filesystem-safe folder name for a course: its label with punctuation
    stripped, falling back to the course id."""
    label = _UNSAFE.sub(" ", bundle.course_label or "").strip()
    label = " ".join(label.split())
    return label or _UNSAFE.sub("-", bundle.course_id).strip("-") or "course"


def course_overview_path(bundle: CourseBundle, vault_dir: Path) -> Path:
    return (
        Path(vault_dir) / _COURSES_DIR / course_folder_name(bundle) / _OVERVIEW_FILENAME
    )


def write_course_overview(bundle: CourseBundle, vault_dir: Path) -> Path:
    """Render and write the course's overview note, creating parent folders.
    Returns the written path."""
    path = course_overview_path(bundle, vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_course_overview(bundle), encoding="utf-8")
    return path


def study_note_path(note: StudyNote, vault_dir: Path) -> Path:
    filename = _safe_name(note.title, fallback=note.assignment_id) + ".md"
    return Path(vault_dir) / _ASSIGNMENTS_DIR / filename


def write_study_note(note: StudyNote, vault_dir: Path) -> Path:
    """Render and write an AI-generated study note to `02 Assignments/`,
    creating the folder. Overwrites in place. Returns the written path."""
    path = study_note_path(note, vault_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_study_note(note), encoding="utf-8")
    return path
