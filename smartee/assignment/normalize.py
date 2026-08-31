"""Turn deterministically-extracted assignment rows into domain records.

`extract_assignments` reads one recon snapshot into `ExtractedAssignment`
values that keep every field exactly as observed (dates as ISO strings,
numbers as-is, no identity). This module pairs those with a caller-supplied
`course_id` and produces `smartee.domain.models.Assignment` — parsing the due
timestamp, validating URLs, and minting a stable synthetic id.

Learning Suite exposes no per-assignment identifier (see
`docs/recon/OBSERVATIONS.md`), so identity is derived from the course id and
the normalized title. A moved deadline therefore stays the *same* assignment
with a changed `due_at` (which is what "detect changed deadlines" needs);
the trade-off is that two assignments with the identical title in one course
would collide. Still pure and deterministic — no network, no clock.
"""

import hashlib
import re
from datetime import datetime

from pydantic import HttpUrl, TypeAdapter, ValidationError

from smartee.assignment.extract import ExtractedAssignment
from smartee.domain.models import Assignment

_WHITESPACE = re.compile(r"\s+")
_HTTP_URL = TypeAdapter(HttpUrl)

# Status words that mean "this row offers a graded-work submission action".
# `Check off` is a completion toggle, not a submission (Hard Rule 4 / D-002).
_SUBMISSION_STATUSES = frozenset({"submit", "view/submit"})


def assignment_identity(course_id: str, title: str) -> str:
    """Stable synthetic id for an assignment: `"<course_id>:<12 hex>"`, the
    hex being a hash of the case- and whitespace-normalized title. Deriving it
    from the title (not the due date) keeps identity stable when a deadline
    moves."""
    normalized = _WHITESPACE.sub(" ", title).strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{course_id}:{digest}"


def normalize_assignment(
    extracted: ExtractedAssignment, *, course_id: str
) -> Assignment:
    """One `ExtractedAssignment` + its `course_id` → one `Assignment`."""
    status = extracted.status_label
    return Assignment(
        id=assignment_identity(course_id, extracted.title),
        course_id=course_id,
        title=extracted.title,
        due_at=_parse_timestamp(extracted.due_at_utc),
        score=extracted.points_earned,
        max_points=extracted.points_possible,
        grade_weight=extracted.grade_weight_percent,
        has_submission_action=(
            extracted.is_actionable
            and (status or "").strip().lower() in _SUBMISSION_STATUSES
        ),
        status=status,
        description=extracted.description,
        external_links=[
            url for raw in extracted.resource_links if (url := _http_url(raw))
        ],
        source_url=_http_url(extracted.provenance.page_url or ""),
    )


def normalize_assignments(
    extracted: list[ExtractedAssignment], *, course_id: str
) -> list[Assignment]:
    """Normalize a list of extracted rows for one course, order preserved."""
    return [normalize_assignment(item, course_id=course_id) for item in extracted]


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string (the row's `<time datetime>`), requiring an
    explicit offset. Returns None for empty, unparseable, or naive input —
    never a naive datetime (`Assignment.due_at` rejects those)."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _http_url(value: str) -> HttpUrl | None:
    try:
        return _HTTP_URL.validate_python(value)
    except ValidationError:
        return None
