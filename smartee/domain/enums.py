from enum import StrEnum


class SourceType(StrEnum):
    """Where a piece of course content originates from."""

    LEARNING_SUITE = "learning_suite"
    BOX = "box"
    YOUTUBE = "youtube"
    EXTERNAL_WEB = "external_web"
    DIRECT_DOCUMENT = "direct_document"
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
