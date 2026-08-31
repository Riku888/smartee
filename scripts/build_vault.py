#!/usr/bin/env python3
"""Build Obsidian notes from local recon captures.

Reads every snapshot in `.local/recon/output/*.json`, runs the deterministic
pipeline (extract assignments -> normalize; content links -> material
manifest; reconcile into a course bundle) and writes one
`01 Courses/<course>/Course Overview.md` per course into the given vault.

With `--study-notes`, also asks the Teacher for one AI study note per
assignment that has a captured description, into `02 Assignments/`. That
step needs an Anthropic credential (`.env` at the repo root is loaded);
model via `SMARTEE_TEACHER_MODEL` (default claude-opus-5).

Overwrites the generated notes in place and touches nothing else.

    uv run python scripts/build_vault.py --vault "/path/to/Obsidian/Vault"
    uv run python scripts/build_vault.py --vault "..." --study-notes
"""

import argparse
import glob
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smartee.assignment import (
    AssignmentListObservation,
    extract_assignments,
    normalize_assignments,
)
from smartee.assignment.extract import AssignmentRowObservation
from smartee.config import load_env
from smartee.course import CourseBundle, assemble_course_bundle
from smartee.llm import LlmUnavailable
from smartee.material import ContentPageObservation, build_manifest
from smartee.obsidian import write_course_overview, write_study_note
from smartee.teacher import build_study_note

DEFAULT_RECON_DIR = Path(".local/recon/output")

_CURRENT_COURSE_PREFIX = "Show course selection menu. Current course: "
_SLUG_UNSAFE = re.compile(r"[^a-z0-9]+")


def _course_label(snapshot: dict) -> str | None:
    """The course the switcher shows as current, or None if not present."""
    for element in snapshot.get("interactive_elements", []):
        aria = (element.get("attributes") or {}).get("aria-label", "")
        if aria.startswith(_CURRENT_COURSE_PREFIX):
            label = aria[len(_CURRENT_COURSE_PREFIX) :].strip()
            return label or None
    return None


def _course_id(label: str) -> str:
    return _SLUG_UNSAFE.sub("-", label.lower()).strip("-") or "course"


def _rows(snapshot: dict) -> list[AssignmentRowObservation]:
    return [
        AssignmentRowObservation(
            control=candidate["control"],
            container=candidate.get("container"),
            description_text=candidate.get("description_text"),
        )
        for candidate in snapshot.get("assignment_row_candidates", [])
    ]


def _write_study_notes(bundle: CourseBundle, vault: Path) -> int:
    """One study note per assignment that has a captured description.
    Returns the count written; stops early on `LlmUnavailable`."""
    described = [a for a in bundle.assignments if a.description]
    if not described:
        return 0
    written = 0
    for assignment in described:
        try:
            note = build_study_note(assignment, now=datetime.now(UTC))
        except LlmUnavailable as exc:
            print(f"  study notes skipped ({exc})")
            break
        path = write_study_note(note, vault)
        print(f"  study note: {assignment.title} -> {path.relative_to(vault)}")
        written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--recon-dir", type=Path, default=DEFAULT_RECON_DIR)
    parser.add_argument(
        "--study-notes",
        action="store_true",
        help="also generate AI study notes (needs an Anthropic credential)",
    )
    args = parser.parse_args()

    load_env(Path(__file__).resolve().parent.parent / ".env")

    if not args.vault.is_dir():
        parser.error(f"vault directory not found: {args.vault}")

    assignments_by_course: dict[str, list] = {}
    materials_by_course: dict[str, list] = {}
    labels: dict[str, str] = {}

    for path in sorted(glob.glob(str(args.recon_dir / "*.json"))):
        for snapshot in json.loads(Path(path).read_text()):
            label = _course_label(snapshot)
            if label is None:
                continue
            course_id = _course_id(label)
            labels[course_id] = label
            url = snapshot.get("url", "")

            if snapshot.get("assignment_row_candidates"):
                result = extract_assignments(
                    AssignmentListObservation(
                        rows=_rows(snapshot),
                        page_url=url,
                        assignments_component_present=snapshot.get(
                            "assignments_component_present"
                        ),
                    )
                )
                assignments_by_course.setdefault(course_id, []).extend(
                    normalize_assignments(result.assignments, course_id=course_id)
                )
            elif "/student/pages/" in url:
                materials_by_course.setdefault(course_id, []).extend(
                    build_manifest(
                        ContentPageObservation(
                            links=snapshot.get("links", []),
                            page_url=url,
                            course_id=course_id,
                        )
                    )
                )

    now = datetime.now(UTC)
    course_ids = sorted(set(assignments_by_course) | set(materials_by_course))
    if not course_ids:
        print("No attributable course data found in recon captures.")
        return

    for course_id in course_ids:
        bundle = assemble_course_bundle(
            course_id=course_id,
            course_label=labels[course_id],
            assignments=assignments_by_course.get(course_id, []),
            materials=materials_by_course.get(course_id, []),
            assembled_at=now,
        )
        written = write_course_overview(bundle, args.vault)
        rel = written.relative_to(args.vault)
        print(
            f"{labels[course_id]}: "
            f"{bundle.summary.assignment_count} assignments, "
            f"{bundle.summary.material_count} materials -> {rel}"
        )
        if args.study_notes:
            _write_study_notes(bundle, args.vault)


if __name__ == "__main__":
    main()
