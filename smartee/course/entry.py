from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin

from smartee.domain.enums import CourseEntryType, SourceType
from smartee.resources.classify import classify_source_type
from smartee.resources.sanitize import domain_of, sanitize_url


@dataclass(frozen=True)
class CourseEntryObservation:
    """A course entry as observed: the Learning Suite entry point that was
    opened and the URL actually seen after navigation settled. Resolver input.

    `entry_url` is the Learning Suite course-entry / source URL (retained as
    provenance and used as the base for standard URL resolution). `final_url`
    is whatever the browser reported after navigation — it may be relative, a
    non-http scheme, or identical to `entry_url`. No navigation is performed
    here; the caller supplies both values.
    """

    entry_url: str
    final_url: str
    observed_at: datetime | None = None


@dataclass(frozen=True)
class CourseEntryProvenance:
    """Where a course entry started. All fields are safe for logs and output."""

    entry_url: str | None
    entry_domain: str | None
    observed_at: datetime | None


@dataclass(frozen=True)
class ResolvedCourseEntry:
    """A deterministically resolved course entry. Every field is safe for logs
    and JSON output — URLs are sanitized.

    `cross_origin` records only whether the host changed between the entry URL
    and the final URL. It is deliberately NOT a statement about authentication,
    session validity, or whether the destination is reachable without a
    separate login — those stay UNKNOWN (OPEN_QUESTIONS.md #2, #3). It is
    `None` when either side has no comparable host.
    """

    entry_type: CourseEntryType
    resolved_url: str | None
    final_domain: str | None
    cross_origin: bool | None
    provenance: CourseEntryProvenance


def resolve_course_entry(observation: CourseEntryObservation) -> ResolvedCourseEntry:
    """Pure, deterministic classification of where a course lives after entry.

    The final URL is resolved against the entry URL with standard URL
    resolution (`urljoin`), so a redirect target expressed as a relative path
    is interpreted the normal way. The entry type is then read from the final
    host alone, reusing `classify_source_type` so "what counts as a Learning
    Suite URL" never diverges from the shared link logic:

    - final host is the Learning Suite host  -> ``learning_suite_native``
    - final URL is a usable http(s) URL on any other host -> ``external_platform``
    - final URL is unusable (relative with no usable base, non-http scheme,
      unparseable) -> ``unknown``

    No host is special-cased beyond the Learning Suite host itself: an external
    destination is classified structurally, never by guessing what a given
    domain "is". No network access, no rendering, no crawling, no LLM.
    """
    resolved_final_raw = urljoin(observation.entry_url, observation.final_url)

    resolved_url = sanitize_url(resolved_final_raw)
    final_domain = domain_of(resolved_final_raw)
    entry_domain = domain_of(observation.entry_url)

    if resolved_url is None or final_domain is None:
        entry_type = CourseEntryType.UNKNOWN
    elif classify_source_type(resolved_final_raw) is SourceType.LEARNING_SUITE:
        entry_type = CourseEntryType.LEARNING_SUITE_NATIVE
    else:
        entry_type = CourseEntryType.EXTERNAL_PLATFORM

    if entry_domain is None or final_domain is None:
        cross_origin: bool | None = None
    else:
        cross_origin = entry_domain != final_domain

    return ResolvedCourseEntry(
        entry_type=entry_type,
        resolved_url=resolved_url,
        final_domain=final_domain,
        cross_origin=cross_origin,
        provenance=CourseEntryProvenance(
            entry_url=sanitize_url(observation.entry_url),
            entry_domain=entry_domain,
            observed_at=observation.observed_at,
        ),
    )
