from pydantic import AwareDatetime, BaseModel, HttpUrl

from smartee.domain.enums import AcquisitionStatus, SourceType


class Course(BaseModel):
    """A single course, as organized by Learning Suite."""

    id: str
    name: str
    code: str | None = None
    term: str | None = None
    source_url: HttpUrl | None = None


class Assignment(BaseModel):
    """An assignment-list entry. Never used to submit work; see D-002."""

    id: str
    course_id: str
    title: str
    due_at: AwareDatetime | None = None
    score: float | None = None
    max_points: float | None = None
    grade_weight: float | None = None
    has_submission_action: bool = False
    # The Learning Suite status/action word as shown on the row, verbatim and
    # sanitized (`Submit`, `Completed`, `Closed`, `Check off`, …). Not an enum:
    # the full set of values is not verified. `None` when it was not observed.
    status: str | None = None
    description: str | None = None
    external_links: list[HttpUrl] = []
    source_url: HttpUrl | None = None


class CourseMaterial(BaseModel):
    """A single piece of course content, normalized regardless of where it lives."""

    id: str
    course_id: str
    title: str
    source_type: SourceType
    status: AcquisitionStatus = AcquisitionStatus.DISCOVERED
    source_url: HttpUrl | None = None
    description: str | None = None


class MaterialManifestEntry(BaseModel):
    """One row of a course/week material manifest (see ARCHITECTURE.md §9)."""

    id: str
    course_id: str
    name: str
    material_type: str | None = None
    status: AcquisitionStatus = AcquisitionStatus.DISCOVERED
    reason: str | None = None
    source_url: HttpUrl | None = None
    discovered_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
