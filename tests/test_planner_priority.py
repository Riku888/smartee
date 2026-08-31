"""Deterministic tests for cross-course assignment prioritization.

Synthetic domain records only; a fixed `now` so urgency is stable.
"""

from datetime import UTC, datetime, timedelta

from smartee.course import assemble_course_bundle
from smartee.domain.models import Assignment
from smartee.planner import RankedAssignment, is_actionable, rank_actionable

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _assignment(
    title,
    *,
    course_id="c1",
    due=None,
    weight=None,
    submit=True,
    score=None,
    status="Submit",
):
    return Assignment(
        id=f"{course_id}:{title}",
        course_id=course_id,
        title=title,
        due_at=due,
        grade_weight=weight,
        has_submission_action=submit,
        score=score,
        status=status,
    )


def _bundle(course_id, label, assignments):
    return assemble_course_bundle(
        course_id=course_id,
        course_label=label,
        assignments=assignments,
        assembled_at=_NOW,
    )


def test_is_actionable_needs_submission_action_and_no_score():
    assert is_actionable(_assignment("a", submit=True, score=None))
    assert not is_actionable(_assignment("a", submit=False))
    assert not is_actionable(_assignment("a", submit=True, score=10.0))


def test_only_actionable_assignments_are_ranked():
    b = _bundle(
        "c1",
        "Course One",
        [
            _assignment("pending", due=_NOW + timedelta(days=2)),
            _assignment("graded", due=_NOW + timedelta(days=1), score=9.0),
            _assignment("no-action", due=_NOW + timedelta(hours=1), submit=False),
        ],
    )
    ranked = rank_actionable([b], now=_NOW)
    assert [r.assignment.title for r in ranked] == ["pending"]


def test_sooner_deadline_outranks_later():
    b = _bundle(
        "c1",
        "Course One",
        [
            _assignment("far", due=_NOW + timedelta(days=20), weight=10),
            _assignment("soon", due=_NOW + timedelta(days=1), weight=10),
        ],
    )
    ranked = rank_actionable([b], now=_NOW)
    assert [r.assignment.title for r in ranked] == ["soon", "far"]
    assert ranked[0].score > ranked[1].score


def test_overdue_ranks_highest_and_reason_says_so():
    b = _bundle(
        "c1",
        "Course One",
        [
            _assignment("tomorrow", due=_NOW + timedelta(days=1), weight=50),
            _assignment("overdue", due=_NOW - timedelta(days=3), weight=1),
        ],
    )
    ranked = rank_actionable([b], now=_NOW)
    assert ranked[0].assignment.title == "overdue"
    assert ranked[0].urgency == 1.0
    assert "overdue by 3 days" in ranked[0].reason


def test_grade_weight_breaks_ties_within_the_same_urgency_bucket():
    b = _bundle(
        "c1",
        "Course One",
        [
            _assignment("light", due=_NOW + timedelta(days=5), weight=2),
            _assignment("heavy", due=_NOW + timedelta(days=6), weight=25),
        ],
    )
    ranked = rank_actionable([b], now=_NOW)
    # Same 7-day urgency bucket -> the heavier assignment wins on impact.
    assert [r.assignment.title for r in ranked] == ["heavy", "light"]


def test_undated_assignment_is_kept_but_sinks_to_the_bottom():
    b = _bundle(
        "c1",
        "Course One",
        [
            _assignment("dated", due=_NOW + timedelta(days=25)),
            _assignment("undated", due=None),
        ],
    )
    ranked = rank_actionable([b], now=_NOW)
    assert [r.assignment.title for r in ranked] == ["dated", "undated"]
    tail = ranked[-1]
    assert tail.days_until_due is None
    assert tail.reason == "no due date captured"


def test_missing_weight_uses_default_impact():
    b = _bundle("c1", "C", [_assignment("x", due=_NOW + timedelta(days=2))])
    (r,) = rank_actionable([b], now=_NOW)
    assert r.impact == 0.3
    assert r.reason == "due in 2 days"


def test_horizon_drops_far_future_but_keeps_overdue_and_undated():
    b = _bundle(
        "c1",
        "C",
        [
            _assignment("far", due=_NOW + timedelta(days=40)),
            _assignment("near", due=_NOW + timedelta(days=3)),
            _assignment("overdue", due=_NOW - timedelta(days=1)),
            _assignment("undated", due=None),
        ],
    )
    ranked = rank_actionable([b], now=_NOW, horizon_days=7)
    titles = {r.assignment.title for r in ranked}
    assert titles == {"near", "overdue", "undated"}


def test_ranks_across_multiple_courses():
    b1 = _bundle(
        "c1", "One", [_assignment("a1", course_id="c1", due=_NOW + timedelta(days=10))]
    )
    b2 = _bundle(
        "c2", "Two", [_assignment("a2", course_id="c2", due=_NOW + timedelta(days=1))]
    )
    ranked = rank_actionable([b1, b2], now=_NOW)
    assert isinstance(ranked[0], RankedAssignment)
    assert ranked[0].course_id == "c2"
    assert ranked[0].course_label == "Two"


def test_empty_input_is_empty_list():
    assert rank_actionable([], now=_NOW) == []
