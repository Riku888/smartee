"""Shared vault-name helpers (used by both `render` and `vault`).

Obsidian resolves `[[wikilinks]]` by note *basename*, so a link's target must
match the file name that `vault` writes — these functions are the single
source of truth for both.
"""

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9 _-]+")


def safe_stem(text: str, *, fallback: str) -> str:
    """A note basename: punctuation collapsed to spaces, whitespace squeezed.
    Falls back to `fallback` when nothing usable remains."""
    cleaned = " ".join(_UNSAFE.sub(" ", text).split())
    return cleaned or fallback


def course_stem(label: str | None, course_id: str) -> str:
    """The folder-note basename for a course (`01 Courses/<stem>/<stem>.md`):
    the label if usable, else a slug of the course id."""
    from_label = " ".join(_UNSAFE.sub(" ", label or "").split())
    return from_label or _UNSAFE.sub("-", course_id).strip("-") or "course"
