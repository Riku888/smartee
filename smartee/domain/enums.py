from enum import StrEnum


class SourceType(StrEnum):
    """Where a piece of course content originates from."""

    LEARNING_SUITE = "learning_suite"
    BOX = "box"
    YOUTUBE = "youtube"
    EXTERNAL_WEB = "external_web"
    DIRECT_DOCUMENT = "direct_document"
    UNKNOWN = "unknown"


class CourseEntryType(StrEnum):
    """Where a course actually lives once its Learning Suite entry is opened.

    Determined deterministically from the final observed URL alone. No claim is
    made about authentication or session reuse — see `smartee.course.entry`.
    """

    LEARNING_SUITE_NATIVE = "learning_suite_native"
    EXTERNAL_PLATFORM = "external_platform"
    UNKNOWN = "unknown"


class AcquisitionStatus(StrEnum):
    """Lifecycle state of a piece of material as it moves through acquisition."""

    DISCOVERED = "discovered"
    ACQUIRED = "acquired"
    PARSED = "parsed"
    INDEXED = "indexed"
    HUMAN_REQUIRED = "human_required"
    MISSING = "missing"
    FAILED = "failed"
    VERIFIED = "verified"
