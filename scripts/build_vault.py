#!/usr/bin/env python3
"""Build Obsidian Course Overview notes from local recon captures.

Reads every snapshot in `.local/recon/output/*.json`, runs the deterministic
pipeline (extract assignments -> normalize; content links -> material
manifest; reconcile into a course bundle) and writes one
`01 Courses/<course>/Course Overview.md` per course into the given vault.

No network, no LLM. Overwrites the generated overview notes in place and
touches nothing else in the vault.

    uv run python scripts/build_vault.py --vault "/path/to/Obsidian/Vault"
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
from smartee.course import assemble_course_bundle
from smartee.material import ContentPageObservation, build_manifest
from smartee.obsidian import write_course_overview

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--recon-dir", type=Path, default=DEFAULT_RECON_DIR)
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
