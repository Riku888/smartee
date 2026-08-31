"""Reconcile everything known about one course into a single bundle.

A course's assignments and materials are read from several page captures
(a dashboard plus the assignments page; one capture per content page), so
the same assignment or file can appear more than once. This composes the
already-normalized pieces — `Assignment` records from
`smartee.assignment` and `MaterialManifestEntry` rows from
`smartee.material` — into one deduplicated, ordered `CourseBundle` with a
small summary the Planner / Obsidian layers can use.

Pure and deterministic: dedup by id, stable sort, no network, no clock.
It does not fetch or navigate — a Collector supplies the captures.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from smartee.domain.models import Assignment, MaterialManifestEntry

# Sorts undated assignments after every dated one without comparing
# datetime to None.
_FAR_FUTURE = datetime.max.replace(tzinfo=UTC)


@dataclass(frozen=True)
class CourseBundleSummary:
    """Counts over one assembled course. All derived, all output-safe."""

    assignment_count: int
    material_count: int
    graded_assignment_count: int
    submission_pending_count: int
    materials_by_type: dict[str, int]


@dataclass(frozen=True)
class CourseBundle:
    """One course's reconciled assignments + materials.

    `assignments` are unique by id, ordered by due date (undated last) then
    title. `materials` are unique by id, ordered by name then id.
    """

    course_id: str
    course_label: str | None
    assignments: list[Assignment]
    materials: list[MaterialManifestEntry]
    summary: CourseBundleSummary
    assembled_at: datetime | None


def assemble_course_bundle(
    *,
    course_id: str,
    course_label: str | None = None,
    assignments: Iterable[Assignment] = (),
    materials: Iterable[MaterialManifestEntry] = (),
    assembled_at: datetime | None = None,
) -> CourseBundle:
    """Deduplicate and order one course's assignments and materials.

    Items whose `course_id` does not match are dropped (the caller built
    them for a different course). Duplicate materials keep the first
    occurrence; duplicate assignments are **merged** field-by-field
    (first-non-empty wins) so a value seen in only one capture — a due
    date from a fresh capture, a description from an expanded row —
    survives even when another capture of the same assignment lacked it.
    """
    merged_assignments = _merge_assignments(
        a for a in assignments if a.course_id == course_id
    )
    deduped_materials = _dedupe(m for m in materials if m.course_id == course_id)

    merged_assignments.sort(key=lambda a: (a.due_at or _FAR_FUTURE, a.title))
    deduped_materials.sort(key=lambda m: (m.name.lower(), m.id))

    summary = CourseBundleSummary(
        assignment_count=len(merged_assignments),
        material_count=len(deduped_materials),
        graded_assignment_count=sum(
            1 for a in merged_assignments if a.score is not None
        ),
        submission_pending_count=sum(
            1 for a in merged_assignments if a.has_submission_action and a.score is None
        ),
        materials_by_type=dict(
            sorted(Counter(m.material_type for m in deduped_materials).items())
        ),
    )

    return CourseBundle(
        course_id=course_id,
        course_label=course_label,
        assignments=merged_assignments,
        materials=deduped_materials,
        summary=summary,
        assembled_at=assembled_at,
    )


def _dedupe(items):
    seen: set[str] = set()
    out = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        out.append(item)
    return out


_EMPTY = (None, "", [])


def _merge_assignments(items: Iterable[Assignment]) -> list[Assignment]:
    """Group `Assignment`s by id (input order preserved); within a group take
    each field's first non-empty value across occurrences."""
    order: list[str] = []
    groups: dict[str, list[Assignment]] = {}
    for item in items:
        if item.id not in groups:
            order.append(item.id)
        groups.setdefault(item.id, []).append(item)

    merged: list[Assignment] = []
    for identity in order:
        group = groups[identity]
        if len(group) == 1:
            merged.append(group[0])
            continue
        data = group[0].model_dump()
        for other in group[1:]:
            for field, value in other.model_dump().items():
                if data.get(field) in _EMPTY and value not in _EMPTY:
                    data[field] = value
        merged.append(Assignment(**data))
    return merged
