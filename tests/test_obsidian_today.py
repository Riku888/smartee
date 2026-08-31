"""Tests for rendering / writing the cross-course Today dashboard."""

from datetime import UTC, datetime, timedelta

from smartee.domain.models import Assignment
from smartee.obsidian import render_today, today_path, write_today
from smartee.planner import RankedAssignment

_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _ranked(title, *, course_label="CYBER 467 - Cybersecurity Pen Test", due_days=2):
    assignment = Assignment(
        id=f"c:{title}",
        course_id="cyber-467",
        title=title,
        due_at=_NOW + timedelta(days=due_days),
        has_submission_action=True,
    )
    return RankedAssignment(
        assignment=assignment,
        course_id="cyber-467",
        course_label=course_label,
        score=0.82,
        urgency=0.8,
        impact=0.3,
        days_until_due=float(due_days),
        reason=f"due in {due_days} days",
    )


def test_render_has_dashboard_frontmatter_and_rows():
    md = render_today(
        [_ranked("TryHackMe Registration"), _ranked("Risk Assessment Phase 2")], _NOW
    )
    assert md.startswith("---\n")
    assert "type: dashboard" in md
    assert "generated: true" in md
    assert "updated: 2026-09-01T12:00:00+00:00" in md
    assert "actionable: 2" in md
    assert "# Today" in md
    assert "| 1 | 0.82 |" in md
    assert "[[TryHackMe Registration\\|TryHackMe Registration]]" in md
    assert (
        "[[CYBER 467 - Cybersecurity Pen Test\\|CYBER 467 - Cybersecurity Pen Test]]"
        in md
    )
    assert "due in 2 days" in md


def test_render_empty_has_placeholder_and_zero_count():
    md = render_today([], _NOW)
    assert "actionable: 0" in md
    assert "Nothing actionable" in md
    assert "| # | Priority |" not in md


def test_rows_are_numbered_in_list_order():
    md = render_today([_ranked("A"), _ranked("B"), _ranked("C")], _NOW)
    assert "| 1 |" in md and "| 2 |" in md and "| 3 |" in md


def test_write_creates_and_overwrites(tmp_path):
    path = write_today([_ranked("A")], tmp_path, generated_at=_NOW)
    assert path == today_path(tmp_path)
    assert path.parent.name == "00 Dashboard"
    assert path.name == "Today.md"
    assert "| 1 |" in path.read_text(encoding="utf-8")

    path2 = write_today([], tmp_path, generated_at=_NOW)
    assert path2 == path
    assert "Nothing actionable" in path.read_text(encoding="utf-8")
