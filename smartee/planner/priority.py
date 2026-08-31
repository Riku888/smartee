"""Rank the student's actionable assignments across all courses.

Deterministic and provisional. ARCHITECTURE §16.1 lists the priority
inputs (deadline urgency, grade impact, dependency blocking, estimated
effort, knowledge weakness, calendar constraints) and says explicitly:

    Do not let an LLM invent exact numerical weights until evaluated
    against real usage.

So this uses a small, transparent, hand-written formula over the only two
inputs currently available from a `CourseBundle` — **deadline urgency**
and **grade impact** — and every ranked item carries the numbers that
produced its score. The formula is expected to change once measured
against the student's real preferences (OPEN_QUESTIONS #9); nothing here
is a decision.

Pure: bundles + a clock reading in, an ordered list out. No network.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from smartee.course.bundle import CourseBundle
from smartee.domain.models import Assignment

# Score = URGENCY_WEIGHT * urgency + IMPACT_WEIGHT * impact, each term in
# [0, 1]. Deadline-dominant on purpose: this feeds a "what do I do today"
# note, not a semester plan.
URGENCY_WEIGHT = 0.7
IMPACT_WEIGHT = 0.3

# Grade weight (percent) is missing on many rows. Treat unknown impact as
# middling-low: it should neither dominate nor be ignored.
_DEFAULT_IMPACT = 0.3

# (max days until due, urgency) — first bucket whose bound is not exceeded
# wins. Overdue and undated are handled before this table.
_URGENCY_BUCKETS: tuple[tuple[float, float], ...] = (
    (1, 0.95),
    (3, 0.80),
    (7, 0.60),
    (14, 0.40),
    (30, 0.20),
)
_URGENCY_FAR = 0.10
_URGENCY_OVERDUE = 1.0
_URGENCY_UNDATED = 0.0


@dataclass(frozen=True)
class RankedAssignment:
    """One actionable assignment with the numbers behind its rank.

    `days_until_due` is negative when overdue, `None` when the assignment
    has no captured due date. `reason` is a short human phrase.
    """

    assignment: Assignment
    course_id: str
    course_label: str | None
    score: float
    urgency: float
    impact: float
    days_until_due: float | None
    reason: str


def is_actionable(assignment: Assignment) -> bool:
    """The assignment still needs work from the student: it exposes a
    submission action and has no score yet. Mirrors the bundle summary's
    `submission_pending_count`."""
    return assignment.has_submission_action and assignment.score is None


def rank_actionable(
    bundles: Iterable[CourseBundle],
    *,
    now: datetime,
    horizon_days: int | None = None,
) -> list[RankedAssignment]:
    """Every actionable assignment across `bundles`, most urgent first.

    `now` must be timezone-aware (it is compared to `Assignment.due_at`).
    With `horizon_days`, assignments due more than that many days out are
    dropped (overdue and undated ones are always kept). Overdue assignments
    are a tier above everything on time; within a tier the order is score,
    then soonest due, then title.
    """
    ranked: list[RankedAssignment] = []
    for bundle in bundles:
        for assignment in bundle.assignments:
            if not is_actionable(assignment):
                continue
            days = _days_until(assignment.due_at, now)
            if horizon_days is not None and days is not None and days > horizon_days:
                continue
            urgency = _urgency(days)
            impact = _impact(assignment.grade_weight)
            ranked.append(
                RankedAssignment(
                    assignment=assignment,
                    course_id=bundle.course_id,
                    course_label=bundle.course_label,
                    score=round(URGENCY_WEIGHT * urgency + IMPACT_WEIGHT * impact, 4),
                    urgency=urgency,
                    impact=round(impact, 4),
                    days_until_due=days,
                    reason=_reason(days, assignment.grade_weight),
                )
            )

    # Overdue work forms its own tier above everything on time, regardless of
    # grade weight — an "act on this now" view should never bury it. Within a
    # tier: score, then soonest due, then title.
    ranked.sort(
        key=lambda r: (
            0 if r.days_until_due is not None and r.days_until_due < 0 else 1,
            -r.score,
            r.days_until_due if r.days_until_due is not None else float("inf"),
            r.assignment.title,
        )
    )
    return ranked


def _days_until(due_at: datetime | None, now: datetime) -> float | None:
    if due_at is None:
        return None
    return (due_at - now).total_seconds() / 86400.0


def _urgency(days: float | None) -> float:
    if days is None:
        return _URGENCY_UNDATED
    if days < 0:
        return _URGENCY_OVERDUE
    for bound, value in _URGENCY_BUCKETS:
        if days <= bound:
            return value
    return _URGENCY_FAR


def _impact(grade_weight: float | None) -> float:
    if grade_weight is None:
        return _DEFAULT_IMPACT
    return max(0.0, min(1.0, grade_weight / 100.0))


def _reason(days: float | None, grade_weight: float | None) -> str:
    if days is None:
        timing = "no due date captured"
    elif days < 0:
        overdue_by = int(abs(days)) or 1
        timing = f"overdue by {overdue_by} day{'s' * (overdue_by != 1)}"
    else:
        remaining = int(days)
        if remaining == 0:
            timing = "due today"
        else:
            timing = f"due in {remaining} day{'s' * (remaining != 1)}"
    if grade_weight is not None:
        weight = (
            int(grade_weight) if grade_weight == int(grade_weight) else grade_weight
        )
        return f"{timing} · {weight}% of grade"
    return timing
