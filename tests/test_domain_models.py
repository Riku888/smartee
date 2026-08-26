from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from smartee.domain import (
    AcquisitionStatus,
    Assignment,
    Course,
    CourseMaterial,
    MaterialManifestEntry,
    SourceType,
)

AWARE_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
NAIVE_NOW = datetime(2026, 1, 15, 12, 0)  # noqa: DTZ001 (intentionally naive, for validation tests)


def test_course_valid_construction():
    course = Course(
        id="cyber465",
        name="Introduction to Cyber Security",
        code="CYBER 465",
        term="Winter 2026",
        source_url="https://learningsuite.byu.edu/course/cyber465",
    )
    assert course.id == "cyber465"
    assert str(course.source_url) == "https://learningsuite.byu.edu/course/cyber465"


def test_course_optional_fields_default_none():
    course = Course(id="cyber465", name="Introduction to Cyber Security")
    assert course.code is None
    assert course.term is None
    assert course.source_url is None


def test_course_serialization_round_trip():
    course = Course(
        id="cyber465", name="Introduction to Cyber Security", code="CYBER 465"
    )
    dumped = course.model_dump()
    assert dumped["code"] == "CYBER 465"
    assert Course.model_validate(dumped) == course


def test_assignment_valid_construction_with_all_fields():
    assignment = Assignment(
        id="lab-05",
        course_id="cyber465",
        title="Lab 5",
        due_at=AWARE_NOW,
        score=95.0,
        max_points=100.0,
        grade_weight=0.1,
        has_submission_action=True,
        description="Kerberos lab",
        external_links=["https://example.com/lab-05"],
        source_url="https://learningsuite.byu.edu/assignment/lab-05",
    )
    assert assignment.due_at == AWARE_NOW
    assert assignment.has_submission_action is True


def test_assignment_optional_fields_missing():
    assignment = Assignment(id="lab-05", course_id="cyber465", title="Lab 5")
    assert assignment.due_at is None
    assert assignment.score is None
    assert assignment.max_points is None
    assert assignment.grade_weight is None
    assert assignment.has_submission_action is False
    assert assignment.external_links == []


def test_assignment_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        Assignment(id="lab-05", course_id="cyber465", title="Lab 5", due_at=NAIVE_NOW)


def test_assignment_accepts_aware_datetime():
    assignment = Assignment(
        id="lab-05", course_id="cyber465", title="Lab 5", due_at=AWARE_NOW
    )
    assert assignment.due_at is not None
    assert assignment.due_at.tzinfo is not None


@pytest.mark.parametrize("source_type", list(SourceType))
def test_course_material_accepts_every_source_type(source_type):
    material = CourseMaterial(
        id="lecture-08-slides",
        course_id="cyber465",
        title="Lecture 8 Slides",
        source_type=source_type,
    )
    assert material.source_type == source_type


def test_course_material_default_status_is_discovered():
    material = CourseMaterial(
        id="lecture-08-slides",
        course_id="cyber465",
        title="Lecture 8 Slides",
        source_type=SourceType.LEARNING_SUITE,
    )
    assert material.status == AcquisitionStatus.DISCOVERED


def test_course_material_serialization_preserves_enum_values():
    material = CourseMaterial(
        id="lecture-08-recording",
        course_id="cyber465",
        title="Lecture 8 Recording",
        source_type=SourceType.YOUTUBE,
        status=AcquisitionStatus.ACQUIRED,
    )
    dumped = material.model_dump(mode="json")
    assert dumped["source_type"] == "youtube"
    assert dumped["status"] == "acquired"


@pytest.mark.parametrize("status", list(AcquisitionStatus))
def test_material_manifest_entry_accepts_every_status(status):
    entry = MaterialManifestEntry(
        id="supplemental-reading",
        course_id="cyber465",
        name="Supplemental Reading",
        status=status,
    )
    assert entry.status == status


def test_material_manifest_entry_optional_fields_missing():
    entry = MaterialManifestEntry(
        id="supplemental-reading", course_id="cyber465", name="Supplemental Reading"
    )
    assert entry.material_type is None
    assert entry.reason is None
    assert entry.source_url is None
    assert entry.discovered_at is None
    assert entry.updated_at is None


def test_material_manifest_entry_human_required_with_reason():
    entry = MaterialManifestEntry(
        id="supplemental-reading",
        course_id="cyber465",
        name="Supplemental Reading",
        material_type="external_article",
        status=AcquisitionStatus.HUMAN_REQUIRED,
        reason="external_authentication_required",
        discovered_at=AWARE_NOW,
    )
    assert entry.status == AcquisitionStatus.HUMAN_REQUIRED
    assert entry.discovered_at is not None
    assert entry.discovered_at.tzinfo is not None


def test_material_manifest_entry_rejects_naive_datetime():
    with pytest.raises(ValidationError):
        MaterialManifestEntry(
            id="supplemental-reading",
            course_id="cyber465",
            name="Supplemental Reading",
            discovered_at=NAIVE_NOW,
        )
