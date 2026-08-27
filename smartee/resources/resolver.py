from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from smartee.domain.enums import SourceType
from smartee.resources.links import build_link_record
from smartee.resources.sanitize import domain_of, sanitize_label, sanitize_url


@dataclass(frozen=True)
class DiscoveredResource:
    """A resource reference exactly as discovered on a page. Resolver input.

    `raw_href` is whatever the DOM returned (possibly relative, possibly a
    non-http scheme). `source_page_url` is the page the reference was found on
    and is used both as the base for standard URL resolution and as retained
    provenance.
    """

    raw_href: str
    source_page_url: str
    link_text: str = ""
    discovered_at: datetime | None = None


@dataclass(frozen=True)
class ResourceProvenance:
    """Where a resolved resource was found. All fields are output-safe."""

    source_page_url: str | None
    source_page_domain: str | None
    discovered_at: datetime | None


@dataclass(frozen=True)
class ResolvedResource:
    """A deterministically normalized resource. Every field is safe for logs
    and JSON output — URLs are sanitized, the label is inert.
    """

    source_type: SourceType
    url: str | None
    domain: str | None
    label: str
    same_origin: bool
    provenance: ResourceProvenance


def resolve_resource(resource: DiscoveredResource) -> ResolvedResource:
    """Pure, deterministic normalization of one discovered resource.

    Relative hrefs are resolved against `source_page_url` with standard URL
    resolution, then classified into a `SourceType`. No network access, no
    crawling, no rendering — classification is from the URL alone, reusing
    `build_link_record` so this never diverges from the shared link logic.

    BYU-external course platforms (Zoom, capstone/support/booklist sites, ...)
    stay `EXTERNAL_WEB`: the recon evidence records only that such links exist,
    never what happens when one is followed (login wall vs. direct access,
    session reuse) — open question #3 in OPEN_QUESTIONS.md. A distinct
    `external_course_platform` type would encode an unverified assumption, so
    it is not added (Hard Rule 2).
    """
    record = build_link_record(
        resource.link_text, resource.raw_href, resource.source_page_url
    )
    return ResolvedResource(
        source_type=SourceType(record["source_type"]),
        url=record["href"],
        domain=record["domain"],
        label=sanitize_label(resource.link_text),
        same_origin=record["same_origin"],
        provenance=ResourceProvenance(
            source_page_url=sanitize_url(resource.source_page_url),
            source_page_domain=domain_of(resource.source_page_url),
            discovered_at=resource.discovered_at,
        ),
    )


def resolve_resources(
    resources: Iterable[DiscoveredResource],
) -> list[ResolvedResource]:
    """Resolve many resources, preserving input order."""
    return [resolve_resource(resource) for resource in resources]
