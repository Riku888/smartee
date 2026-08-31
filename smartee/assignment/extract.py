"""Deterministic extraction of assignment-list rows from a recon capture.

Reconnaissance-driven, not a production selector contract (CLAUDE.md Hard
Rule 1). Every rule below was read directly from two real read-only captures
of the Learning Suite assignments list, across two courses / two instructors
with an identical collapsed-row layout — see
`docs/recon/OBSERVATIONS.md` § "Assignment-list row structure".

Input is the generic `assignment_row_candidates` shape that
`scripts/recon_learning_suite.py` already produces (one matched
action/status control plus a bounded, sanitized capture of its container).
Nothing here navigates, clicks, submits, or reconstructs a value the capture
did not contain: a field that cannot be read deterministically is left
`None`, never guessed (Hard Rules 2 and 3). This layer assigns no identity —
a later step pairs these rows with course context to build
`smartee.domain.models.Assignment` records.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from smartee.resources.sanitize import (
    domain_of,
    sanitize_label,
    sanitize_text_block,
    sanitize_url,
)
from smartee.resources.structure import ContainerStructureRecord, DescendantRecord

# Row-cell positions, relative to a row's inner wrapper, confirmed against the
# list's column headers (`Title | Due | Submission | Score | % of Grade |
# Statistics`). Matched as path *suffixes* so an extra outer wrapper picked up
# by the recon ancestor walk does not matter.
_TITLE_SUFFIX = "/div[2]/span[1]"
_LOCAL_TIME_SUFFIX = "/span[2]/time[1]"
_TIMEZONE_SUFFIX = "/span[2]/span[2]"
_POINTS_POSSIBLE_SUFFIX = "/div[5]/div[1]"
_POINTS_EARNED_FRAGMENT = "/div[5]/div[1]/"
_WEIGHT_CELL_SUFFIX = "/div[6]"


@dataclass(frozen=True)
class AssignmentRowObservation:
    """One captured assignments-list row candidate.

    `control`, `container`, and `description_text` are exactly the
    `assignment_row_candidates[i]` sub-objects from a recon snapshot
    (`control` is the matched action/status element; `container` is the
    bounded structural capture of its row, or `None` when the walk found no
    ancestor to capture; `description_text` is the expanded row's description
    body when it was open at capture time, else `None`).
    """

    control: dict
    container: ContainerStructureRecord | None
    description_text: str | None = None
    described_assignment_title: str | None = None


@dataclass(frozen=True)
class AssignmentListObservation:
    """A recon snapshot's assignment-row candidates for one page.

    `assignments_component_present` is the snapshot's
    `assignments_component_present` flag (whether `#assignmentsComponent` was
    in the DOM). When known it decides `is_assignment_list` directly — the
    Exam List view renders at the same URL without that element. Leave it
    `None` for older captures that predate the flag.
    """

    rows: Sequence[AssignmentRowObservation]
    page_url: str
    observed_at: datetime | None = None
    assignments_component_present: bool | None = None


@dataclass(frozen=True)
class AssignmentExtractionProvenance:
    """Where a set of extracted rows was read from. All fields output-safe."""

    page_url: str | None
    page_domain: str | None
    observed_at: datetime | None


@dataclass(frozen=True)
class ExtractedAssignment:
    """One assignments-list row, read deterministically. Output-safe.

    `due_at_utc` is the verbatim `datetime` attribute of the row's `<time>`
    element (an absolute UTC ISO timestamp) — authoritative, and `None` when
    the element carried no such attribute. `due_local_text` / `due_timezone`
    are the human-facing strings shown in the row and are NOT parsed into a
    timestamp here. `status_label` is the row control's word as shown
    (`Submit`, `Completed`, `Closed`, …); `is_actionable` is True only when
    that control was a real `<button>`.
    """

    title: str
    due_at_utc: str | None
    due_local_text: str | None
    due_timezone: str | None
    status_label: str | None
    is_actionable: bool
    points_possible: float | None
    points_earned: float | None
    grade_weight_percent: float | None
    weighted_points_earned: float | None
    description: str | None
    resource_links: list[str]
    provenance: AssignmentExtractionProvenance


@dataclass(frozen=True)
class AssignmentExtractionResult:
    """Result of one extraction pass.

    `is_assignment_list` reflects the snapshot's
    `assignments_component_present` flag when it was recorded; otherwise it
    falls back to "at least one candidate row parsed". False with an empty
    `assignments` list is not an error — the capture was of a different view
    (e.g. the Exam List at the same URL) or the list was genuinely empty.
    """

    is_assignment_list: bool
    assignments: list[ExtractedAssignment]


def extract_assignments(
    observation: AssignmentListObservation,
) -> AssignmentExtractionResult:
    """Pure, deterministic read of assignment rows from one recon snapshot.

    A candidate is kept only if its container exposes the VERIFIED row
    signature (a title span at `…/div[2]/span[1]`). Detail-panel controls and
    empty Exam-List `View` candidates carry no such span and are skipped, not
    guessed. Rows are de-duplicated on (title, `due_at_utc`), first
    occurrence winning and input order preserved. No network, no navigation,
    no clicking, no LLM.
    """
    provenance = AssignmentExtractionProvenance(
        page_url=sanitize_url(observation.page_url),
        page_domain=domain_of(observation.page_url),
        observed_at=observation.observed_at,
    )

    seen: set[tuple[str, str | None]] = set()
    assignments: list[ExtractedAssignment] = []
    for row in observation.rows:
        extracted = _extract_row(row, provenance)
        if extracted is None:
            continue
        key = (extracted.title, extracted.due_at_utc)
        if key in seen:
            continue
        seen.add(key)
        assignments.append(extracted)

    assignments = _attach_orphan_descriptions(assignments, observation.rows)

    if observation.assignments_component_present is None:
        is_assignment_list = bool(assignments)
    else:
        is_assignment_list = observation.assignments_component_present

    return AssignmentExtractionResult(
        is_assignment_list=is_assignment_list,
        assignments=assignments,
    )


# A description panel's first line is "Due: <Mon> <D> <h>:<mm> <am|pm> <TZ>".
_DUE_LINE = re.compile(
    r"Due:\s*([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})\s*(am|pm)\s*([A-Z]{2,4})"
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ),
        start=1,
    )
}
# BYU is Mountain Time; only these appear in the captures.
_TZ_OFFSET_HOURS = {"MDT": -6, "MST": -7}


def _attach_orphan_descriptions(
    assignments: list[ExtractedAssignment],
    rows: Sequence[AssignmentRowObservation],
) -> list[ExtractedAssignment]:
    """When a row was expanded at capture time, its description panel and its
    list row are captured as separate candidates. Re-attach a description that
    did not land on a titled assignment: first by the row title the recon
    recorded for it, else by matching the panel's "Due:" line to an
    assignment's `due_at_utc`. Only fills a description that is still empty.
    """
    by_index = {i: a for i, a in enumerate(assignments)}
    by_title = {_norm(a.title): i for i, a in enumerate(assignments)}

    for row in rows:
        text = row.description_text
        if not text:
            continue
        if any(a.description == text for a in assignments):
            continue  # already attached to its own titled row

        target = by_title.get(_norm(row.described_assignment_title or ""))
        if target is None:
            target = _match_by_due_line(text, assignments)
        if target is None or by_index[target].description:
            continue
        by_index[target] = replace(by_index[target], description=text)

    return list(by_index.values())


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _match_by_due_line(
    description: str, assignments: Sequence[ExtractedAssignment]
) -> int | None:
    match = _DUE_LINE.search(description)
    if match is None:
        return None
    mon, day, hour12, minute, ampm, tz = match.groups()
    if mon not in _MONTHS or tz not in _TZ_OFFSET_HOURS:
        return None
    hour = int(hour12) % 12 + (12 if ampm == "pm" else 0)
    try:
        local = datetime(2000, _MONTHS[mon], int(day), hour, int(minute), tzinfo=UTC)
    except ValueError:
        return None
    wanted_utc = local - timedelta(hours=_TZ_OFFSET_HOURS[tz])

    hits = [
        i
        for i, a in enumerate(assignments)
        if not a.description and _same_month_day_time(a.due_at_utc, wanted_utc)
    ]
    return hits[0] if len(hits) == 1 else None


def _same_month_day_time(due_at_utc: str | None, wanted: datetime) -> bool:
    if not due_at_utc:
        return False
    try:
        got = datetime.fromisoformat(due_at_utc)
    except ValueError:
        return False
    return (got.month, got.day, got.hour, got.minute) == (
        wanted.month,
        wanted.day,
        wanted.hour,
        wanted.minute,
    )


def _extract_row(
    row: AssignmentRowObservation,
    provenance: AssignmentExtractionProvenance,
) -> ExtractedAssignment | None:
    container = row.container
    if container is None:
        return None
    descendants = container.get("descendants") or []

    title = _first_text(descendants, suffix=_TITLE_SUFFIX, tag="span")
    if title is None:
        return None

    possible_raw = _first_text(descendants, suffix=_POINTS_POSSIBLE_SUFFIX)
    earned_raw = _first_text(descendants, fragment=_POINTS_EARNED_FRAGMENT, tag="b")
    weighted_earned, weight_percent = _weight_cell(
        _first_text(descendants, suffix=_WEIGHT_CELL_SUFFIX, tag="div")
    )

    control = row.control or {}
    attributes = control.get("attributes") or {}
    status_label = sanitize_label(
        control.get("label") or attributes.get("aria-label") or ""
    )

    return ExtractedAssignment(
        title=title,
        due_at_utc=_datetime_attr(descendants),
        due_local_text=_first_text(descendants, suffix=_LOCAL_TIME_SUFFIX, tag="time"),
        due_timezone=_first_text(descendants, suffix=_TIMEZONE_SUFFIX, tag="span"),
        status_label=status_label or None,
        is_actionable=control.get("tag") == "button",
        points_possible=_parse_number(possible_raw),
        points_earned=_parse_number(earned_raw),
        grade_weight_percent=weight_percent,
        weighted_points_earned=weighted_earned,
        description=_description(row.description_text),
        resource_links=_resource_links(container),
        provenance=provenance,
    )


def _first_text(
    descendants: Sequence[DescendantRecord],
    *,
    suffix: str | None = None,
    fragment: str | None = None,
    tag: str | None = None,
) -> str | None:
    """First descendant (document order) matching tag / path suffix / path
    fragment and carrying non-empty text; its sanitized text, else None."""
    for descendant in descendants:
        if tag is not None and descendant.get("tag") != tag:
            continue
        path = descendant.get("path") or ""
        if suffix is not None and not path.endswith(suffix):
            continue
        if fragment is not None and fragment not in path:
            continue
        text = sanitize_label(descendant.get("text") or "")
        if text:
            return text
    return None


def _datetime_attr(descendants: Sequence[DescendantRecord]) -> str | None:
    """The first `<time>` element's `datetime` attribute value, or None."""
    for descendant in descendants:
        if descendant.get("tag") != "time":
            continue
        value = (descendant.get("attributes") or {}).get("datetime")
        if value:
            return value
    return None


def _weight_cell(text: str | None) -> tuple[float | None, float | None]:
    """Split the `…/div[6]` cell into (weighted_points_earned,
    grade_weight_percent). The usual form is `"<weighted earned> /<weight>%"`
    (`"6.67 /6.67%"`); a genuinely ungraded assignment shows just the weight
    (`"0%"`, no `/`). Either side may be unparseable, in which case that side
    is None."""
    if not text:
        return (None, None)
    if "/" not in text:
        return (None, _parse_number(text))
    left, _, right = text.partition("/")
    return (_parse_number(left), _parse_number(right))


def _parse_number(text: str | None) -> float | None:
    """Lenient float parse: strips surrounding whitespace and a trailing
    `%`. Returns None for empty or non-numeric input — never raises."""
    if not text:
        return None
    cleaned = text.strip().rstrip("%").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _description(text: str | None) -> str | None:
    """Re-sanitize the recon capture's description block (idempotent defence in
    depth — the value is still untrusted course-authored text)."""
    if not text:
        return None
    return sanitize_text_block(text) or None


def _resource_links(container: ContainerStructureRecord) -> list[str]:
    """Sanitized hrefs of links captured inside the row container (populated
    only when the row was expanded at capture time)."""
    links = container.get("links") or []
    return [href for link in links if (href := link.get("href"))]
