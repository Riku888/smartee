import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from smartee.resources.interactive import InteractiveElementRecord
from smartee.resources.sanitize import domain_of, sanitize_label, sanitize_url

# The course-selection menu toggle observed in the clean in-course Course
# Switcher capture: a <button> whose aria-label begins with this text. When it
# is expanded its aria-expanded attribute reads "true" and the menu's course
# <a> entries are present in the DOM. When collapsed ("No course selected" /
# aria-expanded "false") the entries are not rendered, so no course may be
# read from that capture (contract rule 2).
_MENU_TOGGLE_ARIA_PREFIX = "show course selection menu"

# A course entry's resolved href path contains this segment, e.g.
# `/.MjTJ/student/cid--tQDtJf5AeQC/student/home/dashboard`. The opaque token
# after `cid-` is the durable course id. `All Courses` and other nav links
# resolve to paths without this segment (e.g. `/student/student/top`) and are
# therefore excluded structurally, never by matching their label text.
_COURSE_PATH_RE = re.compile(r"/student/cid-([A-Za-z0-9_-]+)/")


@dataclass(frozen=True)
class CourseMenuObservation:
    """One observation of the course-selection menu, as generic interactive
    records. Discovery input.

    `elements` is whatever the recon capture returned for the page — the same
    `InteractiveElementRecord` shape produced for any page, not a
    course-specific structure. `menu_page_url` is the page the menu was
    observed on (retained as provenance and sanitized before output).

    `observed_term` is a term string only when the observer directly saw one
    scoping this exact menu (e.g. a heading over the list). It must never be
    inferred from a course label or from "the current course's term"; leave it
    None when no term was directly observed.
    """

    elements: Sequence[InteractiveElementRecord]
    menu_page_url: str
    observed_at: datetime | None = None
    observed_term: str | None = None


@dataclass(frozen=True)
class CourseDiscoveryProvenance:
    """Where a set of discovered courses was read from. All fields output-safe."""

    menu_page_url: str | None
    menu_page_domain: str | None
    observed_at: datetime | None


@dataclass(frozen=True)
class DiscoveredCourse:
    """A single course read deterministically from an expanded course-selection
    menu. Every field is safe for logs and JSON output.

    No claim is made about whether the course is published, available, or
    reachable without a separate login — those stay UNKNOWN. `term` is None
    unless a term was directly observed scoping the menu.
    """

    course_id: str
    label: str
    entry_url: str
    term: str | None
    provenance: CourseDiscoveryProvenance


@dataclass(frozen=True)
class CourseDiscoveryResult:
    """Result of one discovery pass.

    `menu_expanded` is False when the observation contains no expanded
    course-selection menu; `courses` is then always empty. It is not an error
    — it means this capture cannot answer "what courses exist".
    """

    menu_expanded: bool
    courses: list[DiscoveredCourse]


def discover_courses(observation: CourseMenuObservation) -> CourseDiscoveryResult:
    """Pure, deterministic enumeration of courses from an observed menu.

    Only runs when the course-selection menu was observed expanded (its toggle
    <button> present with aria-expanded "true"). For every <a> record whose
    sanitized resolved href path contains `/student/cid-<id>/`, the opaque
    `cid-` token is taken as the course id and used as the identity /
    deduplication key (first occurrence wins, input order preserved).

    Anything that does not match that exact structure — a non-<a> record, a
    missing or non-http href, a `cid-` segment with no token — is skipped, not
    guessed. No network access, no navigation, no clicking, no crawling, no
    LLM, and no reconstruction of URLs from a course id.
    """
    if not _menu_is_expanded(observation.elements):
        return CourseDiscoveryResult(menu_expanded=False, courses=[])

    provenance = CourseDiscoveryProvenance(
        menu_page_url=sanitize_url(observation.menu_page_url),
        menu_page_domain=domain_of(observation.menu_page_url),
        observed_at=observation.observed_at,
    )
    term = _sanitized_term(observation.observed_term)

    seen: set[str] = set()
    courses: list[DiscoveredCourse] = []
    for element in observation.elements:
        course = _course_from_element(element, term, provenance)
        if course is None or course.course_id in seen:
            continue
        seen.add(course.course_id)
        courses.append(course)

    return CourseDiscoveryResult(menu_expanded=True, courses=courses)


def _menu_is_expanded(elements: Sequence[InteractiveElementRecord]) -> bool:
    for element in elements:
        if element["tag"] != "button":
            continue
        aria_label = (element["attributes"].get("aria-label") or "").strip().lower()
        if aria_label.startswith(_MENU_TOGGLE_ARIA_PREFIX):
            expanded = element["attributes"].get("aria-expanded") or ""
            return expanded.strip().lower() == "true"
    return False


def _sanitized_term(raw: str | None) -> str | None:
    if raw is None:
        return None
    return sanitize_label(raw) or None


def _course_from_element(
    element: InteractiveElementRecord,
    term: str | None,
    provenance: CourseDiscoveryProvenance,
) -> DiscoveredCourse | None:
    if element["tag"] != "a":
        return None

    link = element["link"]
    if link is None:
        return None
    href = link["href"]
    if href is None:
        return None

    try:
        path = urlparse(href).path
    except ValueError:
        return None

    match = _COURSE_PATH_RE.search(path)
    if match is None:
        return None

    return DiscoveredCourse(
        course_id=match.group(1),
        label=sanitize_label(element["label"]),
        entry_url=href,
        term=term,
        provenance=provenance,
    )
