"""Deterministic tests for course-bundle assembly.

Synthetic domain records only.
"""

from datetime import UTC, datetime

from smartee.course import assemble_course_bundle
from smartee.domain.enums import AcquisitionStatus
from smartee.domain.models import Assignment, MaterialManifestEntry

_C = "cid-abc"


def _assignment(id_, *, course_id=_C, due=None, score=None, submit=False, title="A"):
    return Assignment(
        id=id_,
        course_id=course_id,
        title=title,
        due_at=due,
        score=score,
        has_submission_action=submit,
    )


def _material(id_, *, course_id=_C, name="File", mtype="learning_suite_file"):
    return MaterialManifestEntry(
        id=id_,
        course_id=course_id,
        name=name,
        material_type=mtype,
        status=AcquisitionStatus.DISCOVERED,
    )


def test_empty_bundle():
    b = assemble_course_bundle(course_id=_C, course_label="Course X")
    assert b.course_label == "Course X"
    assert b.assignments == []
    assert b.materials == []
    assert b.summary.assignment_count == 0
    assert b.summary.materials_by_type == {}


def test_deduplicates_by_id_first_wins():
    a1 = _assignment("a", title="first")
    a2 = _assignment("a", title="second")
    m1 = _material("m", name="one")
    m2 = _material("m", name="two")
    b = assemble_course_bundle(course_id=_C, assignments=[a1, a2], materials=[m1, m2])
    assert [a.title for a in b.assignments] == ["first"]
    assert [m.name for m in b.materials] == ["one"]


def test_drops_items_from_a_different_course():
    b = assemble_course_bundle(
        course_id=_C,
        assignments=[_assignment("a"), _assignment("b", course_id="other")],
        materials=[_material("m"), _material("n", course_id="other")],
    )
    assert [a.id for a in b.assignments] == ["a"]
    assert [m.id for m in b.materials] == ["m"]


def test_assignments_sorted_by_due_then_title_undated_last():
    early = _assignment("e", due=datetime(2026, 1, 1, tzinfo=UTC), title="early")
    late = _assignment("l", due=datetime(2026, 6, 1, tzinfo=UTC), title="late")
    undated_a = _assignment("ua", title="alpha")
    undated_b = _assignment("ub", title="beta")
    b = assemble_course_bundle(
        course_id=_C, assignments=[undated_b, late, undated_a, early]
    )
    assert [a.id for a in b.assignments] == ["e", "l", "ua", "ub"]


def test_materials_sorted_by_name_case_insensitive():
    b = assemble_course_bundle(
        course_id=_C,
        materials=[
            _material("1", name="zeta"),
            _material("2", name="Alpha"),
            _material("3", name="beta"),
        ],
    )
    assert [m.name for m in b.materials] == ["Alpha", "beta", "zeta"]


def test_summary_counts():
    b = assemble_course_bundle(
        course_id=_C,
        assignments=[
            _assignment("a", score=9.0),
            _assignment("b", submit=True),
            _assignment("c", submit=True, score=5.0),
            _assignment("d"),
        ],
        materials=[
            _material("m", mtype="learning_suite_file"),
            _material("n", mtype="learning_suite_file"),
            _material("o", mtype="box_file"),
        ],
    )
    s = b.summary
    assert s.assignment_count == 4
    assert s.material_count == 3
    assert s.graded_assignment_count == 2  # a, c
    assert s.submission_pending_count == 1  # b only (c is graded)
    assert s.materials_by_type == {"box_file": 1, "learning_suite_file": 2}
