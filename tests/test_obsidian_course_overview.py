"""Deterministic tests for the Obsidian Course Overview note.

Synthetic `CourseBundle`s only.
"""

from datetime import UTC, datetime

from smartee.course import assemble_course_bundle
from smartee.domain.enums import AcquisitionStatus
from smartee.domain.models import Assignment, MaterialManifestEntry
from smartee.obsidian import (
    course_folder_name,
    course_overview_path,
    render_course_overview,
    write_course_overview,
)

_C = "cid-abc"


def _bundle(*, label="Defensive Cybersecurity", assignments=(), materials=()):
    return assemble_course_bundle(
        course_id=_C,
        course_label=label,
        assignments=assignments,
        materials=materials,
        assembled_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
    )


def _assignment(id_, **kw):
    return Assignment(id=id_, course_id=_C, title=kw.pop("title", "A"), **kw)


def _material(id_, **kw):
    return MaterialManifestEntry(
        id=id_,
        course_id=_C,
        name=kw.pop("name", "File"),
        material_type=kw.pop("material_type", "learning_suite_file"),
        status=kw.pop("status", AcquisitionStatus.DISCOVERED),
        **kw,
    )


# --- render ----------------------------------------------------------


def test_render_has_frontmatter_title_and_notice():
    md = render_course_overview(_bundle())
    assert md.startswith("---\n")
    assert "type: course-overview" in md
    assert "course_id: cid-abc" in md
    assert "\n# Defensive Cybersecurity\n" in md
    assert "Auto-generated" in md


def test_render_empty_sections():
    md = render_course_overview(_bundle())
    assert "## Assignments\n\n_None found._" in md
    assert "## Materials\n\n_None found._" in md
    assert "assignments: 0" in md


def test_render_assignment_row():
    a = _assignment(
        "a",
        title="Lab 1: GRC",
        due_at=datetime(2026, 9, 16, 19, 0, tzinfo=UTC),
        status="Completed",
        score=48.0,
        max_points=50.0,
        grade_weight=5.0,
    )
    md = render_course_overview(_bundle(assignments=[a]))
    assert "| 2026-09-16 19:00 | Lab 1: GRC | Completed | 48 / 50 | 5% |" in md
    assert "graded_assignments: 1" in md


def test_render_missing_fields_render_as_dash():
    a = _assignment("a", title="Team assignment")
    md = render_course_overview(_bundle(assignments=[a]))
    assert "| — | Team assignment | — | — | — |" in md


def test_render_pipe_in_title_is_escaped():
    a = _assignment("a", title="A | B")
    md = render_course_overview(_bundle(assignments=[a]))
    assert "A \\| B" in md


def test_render_material_row_with_and_without_link():
    m1 = _material("m1", name="Slides", source_url="https://byu.box.com/s/x")
    m2 = _material("m2", name="Learning Suite file")
    md = render_course_overview(_bundle(materials=[m1, m2]))
    assert (
        "| Slides | learning_suite_file | discovered | [open](https://byu.box.com/s/x) |"
        in md
    )
    assert "| Learning Suite file | learning_suite_file | discovered | — |" in md


def test_render_summary_line_counts_materials_by_type():
    md = render_course_overview(
        _bundle(
            materials=[
                _material("m1", material_type="learning_suite_file"),
                _material("m2", material_type="learning_suite_file"),
                _material("m3", material_type="box_file", name="B"),
            ]
        )
    )
    assert "Materials: 3 — 1 box_file, 2 learning_suite_file" in md


# --- vault paths / write --------------------------------------------


def test_course_folder_name_strips_punctuation():
    assert course_folder_name(_bundle(label="IT&C 366 – Defensive")) == (
        "IT C 366 Defensive"
    )


def test_course_folder_name_falls_back_to_course_id():
    assert course_folder_name(_bundle(label=None)) == "cid-abc"


def test_write_course_overview_creates_file(tmp_path):
    path = write_course_overview(_bundle(), tmp_path)
    assert path == course_overview_path(_bundle(), tmp_path)
    assert path.parent.name == "Defensive Cybersecurity"
    assert path.parent.parent.name == "01 Courses"
    assert path.read_text(encoding="utf-8").startswith("---\n")


def test_write_course_overview_overwrites(tmp_path):
    write_course_overview(_bundle(), tmp_path)
    path = write_course_overview(
        _bundle(assignments=[_assignment("a", title="New")]), tmp_path
    )
    text = path.read_text(encoding="utf-8")
    assert "New" in text
    assert "_None found._" not in text.split("## Assignments")[1].split("##")[0]
