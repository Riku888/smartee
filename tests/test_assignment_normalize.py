"""Deterministic tests for assignment normalization.

Synthetic `ExtractedAssignment` inputs only — no real course data.
"""

from datetime import UTC, datetime

from smartee.assignment import (
    assignment_identity,
    normalize_assignment,
    normalize_assignments,
)
from smartee.assignment.extract import (
    AssignmentExtractionProvenance,
    ExtractedAssignment,
)

_PROV = AssignmentExtractionProvenance(
    page_url="https://learningsuite.byu.edu/.x/cid-abc/student/home/assignments",
    page_domain="learningsuite.byu.edu",
    observed_at=None,
)


def _extracted(**overrides) -> ExtractedAssignment:
    base = {
        "title": "Lab One",
        "due_at_utc": "2026-09-16T19:00:00.000Z",
        "due_local_text": "1:00 pm",
        "due_timezone": "MDT",
        "status_label": "Submit",
        "is_actionable": True,
        "points_possible": 10.0,
        "points_earned": None,
        "grade_weight_percent": 4.17,
        "weighted_points_earned": 0.0,
        "description": None,
        "resource_links": [],
        "provenance": _PROV,
    }
    base.update(overrides)
    return ExtractedAssignment(**base)


# --- assignment_identity -------------------------------------------------


def test_identity_shape_and_prefix():
    identity = assignment_identity("cid-abc", "Lab One")
    assert identity.startswith("cid-abc:")
    assert len(identity.split(":", 1)[1]) == 12


def test_identity_is_stable_across_whitespace_and_case():
    assert assignment_identity("c", "Lab  One") == assignment_identity("c", "lab one")


def test_identity_differs_by_title_and_course():
    assert assignment_identity("c", "Lab One") != assignment_identity("c", "Lab Two")
    assert assignment_identity("c1", "Lab One") != assignment_identity("c2", "Lab One")


def test_identity_independent_of_due_date():
    a = normalize_assignment(
        _extracted(due_at_utc="2026-09-16T19:00:00Z"), course_id="c"
    )
    b = normalize_assignment(
        _extracted(due_at_utc="2026-10-01T19:00:00Z"), course_id="c"
    )
    assert a.id == b.id
    assert a.due_at != b.due_at


# --- field mapping -----------------------------------------------------


def test_full_mapping():
    a = normalize_assignment(
        _extracted(
            status_label="Completed",
            is_actionable=False,
            points_earned=9.0,
            points_possible=10.0,
            grade_weight_percent=6.67,
            description="Read chapters 3-4.",
            resource_links=[
                "https://learningsuite.byu.edu/x/fileDownload.php?fileId=z"
            ],
        ),
        course_id="cid-abc",
    )
    assert a.course_id == "cid-abc"
    assert a.title == "Lab One"
    assert a.due_at == datetime(2026, 9, 16, 19, 0, tzinfo=UTC)
    assert a.score == 9.0
    assert a.max_points == 10.0
    assert a.grade_weight == 6.67
    assert a.status == "Completed"
    assert a.has_submission_action is False
    assert a.description == "Read chapters 3-4."
    assert [str(u) for u in a.external_links] == [
        "https://learningsuite.byu.edu/x/fileDownload.php?fileId=z"
    ]
    assert str(a.source_url).startswith("https://learningsuite.byu.edu/")


def test_status_passed_through_verbatim_including_none():
    assert (
        normalize_assignment(_extracted(status_label=None), course_id="c").status
        is None
    )
    assert (
        normalize_assignment(_extracted(status_label="Check off"), course_id="c").status
        == "Check off"
    )


# --- has_submission_action -------------------------------------------


def test_submission_action_true_only_for_actionable_submit():
    assert (
        normalize_assignment(
            _extracted(status_label="Submit", is_actionable=True), course_id="c"
        ).has_submission_action
        is True
    )
    assert (
        normalize_assignment(
            _extracted(status_label="View/Submit", is_actionable=True), course_id="c"
        ).has_submission_action
        is True
    )


def test_submission_action_false_for_checkoff_completed_or_non_actionable():
    for status, actionable in [
        ("Check off", True),
        ("Completed", False),
        ("Closed", False),
        ("Submit", False),
    ]:
        a = normalize_assignment(
            _extracted(status_label=status, is_actionable=actionable), course_id="c"
        )
        assert a.has_submission_action is False


# --- due timestamp parsing ------------------------------------------


def test_due_at_variants():
    assert (
        normalize_assignment(_extracted(due_at_utc=None), course_id="c").due_at is None
    )
    assert (
        normalize_assignment(_extracted(due_at_utc="not-a-date"), course_id="c").due_at
        is None
    )
    # naive (no offset) is rejected rather than passed through
    assert (
        normalize_assignment(
            _extracted(due_at_utc="2026-09-16T19:00:00"), course_id="c"
        ).due_at
        is None
    )
    aware = normalize_assignment(
        _extracted(due_at_utc="2026-09-16T19:00:00.000Z"), course_id="c"
    ).due_at
    assert aware is not None and aware.tzinfo is not None


# --- urls -------------------------------------------------------------


def test_invalid_resource_links_are_dropped():
    a = normalize_assignment(
        _extracted(resource_links=["/relative/path", "", "https://ok.example/x"]),
        course_id="c",
    )
    assert [str(u) for u in a.external_links] == ["https://ok.example/x"]


def test_source_url_none_when_provenance_url_missing():
    prov = AssignmentExtractionProvenance(
        page_url=None, page_domain=None, observed_at=None
    )
    a = normalize_assignment(_extracted(provenance=prov), course_id="c")
    assert a.source_url is None


# --- list --------------------------------------------------------------


def test_normalize_assignments_preserves_order():
    items = [_extracted(title=f"Task {i}") for i in range(4)]
    out = normalize_assignments(items, course_id="c")
    assert [a.title for a in out] == ["Task 0", "Task 1", "Task 2", "Task 3"]
