"""Tests for rendering / writing an AI study note into the vault."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from smartee.obsidian import render_study_note, study_note_path, write_study_note
from smartee.teacher import StudyNote

_NOTE = StudyNote(
    assignment_id="cid-x:abc123",
    course_id="cid-x",
    title="Lab 4: Firewall/VPN",
    markdown="## What this is really asking\n\nConfigure a VPN.\n",
    model="claude-opus-5",
    generated_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
)


def test_render_has_ai_frontmatter_and_notice():
    md = render_study_note(_NOTE)
    assert md.startswith("---\n")
    assert "type: study-note" in md
    assert "ai_generated: true" in md
    assert "assignment_id: cid-x:abc123" in md
    assert "model: claude-opus-5" in md
    assert "generated: 2026-08-31T12:00:00+00:00" in md
    assert "# Lab 4: Firewall/VPN" in md
    assert "AI-generated study aid" in md
    assert "## What this is really asking" in md


def test_render_generated_none_is_null():
    note = StudyNote(
        assignment_id="a",
        course_id="c",
        title="T",
        markdown="## x",
        model="m",
        generated_at=None,
    )
    assert "generated: null" in render_study_note(note)


def test_path_sanitizes_title():
    path = study_note_path(_NOTE, Path("/vault"))
    assert path.name == "Lab 4 Firewall VPN.md"
    assert path.parent.name == "02 Assignments"


def test_write_creates_and_overwrites(tmp_path):
    path = write_study_note(_NOTE, tmp_path)
    assert path == study_note_path(_NOTE, tmp_path)
    assert path.read_text(encoding="utf-8").startswith("---\n")

    updated = replace(_NOTE, markdown="## changed\n\nnew body")
    path2 = write_study_note(updated, tmp_path)
    assert path2 == path
    assert "new body" in path.read_text(encoding="utf-8")
