"""Build a per-course material manifest from a captured content page.

Reconnaissance-driven (see `docs/recon/OBSERVATIONS.md` § "Course navigation
+ content pages"). A Learning Suite content page (`student/pages/id-*`) is an
instructor-authored rich-text block with resource links inline: file
downloads (`.../plugins/Upload/fileDownload.php?fileId=<opaque>`) and
cross-origin links (Box, YouTube, external sites). This turns one such page's
links into `MaterialManifestEntry` rows.

Deterministic and URL-only — no network, no rendering, no crawling. A
material's real filename/title is not on the page (a download link's text is
just "Download"); it is left as a readable placeholder here and resolved
later at acquisition time (roadmap: Material Acquisition) from the HTTP
response. Enumerating every content page of a course is a separate concern
(roadmap: Course traversal); this operates on one already-captured page.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from pydantic import HttpUrl, TypeAdapter, ValidationError

from smartee.domain.enums import AcquisitionStatus, SourceType
from smartee.domain.models import MaterialManifestEntry
from smartee.resources.links import LinkRecord
from smartee.resources.sanitize import sanitize_label

_HTTP_URL = TypeAdapter(HttpUrl)

# A Learning Suite file download resolves to this path (same-origin, so it
# cannot be told from in-app navigation by origin alone — match the path).
_FILE_DOWNLOAD_PATH = "/plugins/Upload/fileDownload.php"

# Cross-origin hosts that are Learning Suite / BYU site chrome, never a course
# material (they appear on every page).
_CHROME_HOSTS = frozenset({"softwaresupport.byu.edu", "learnanywhere.byu.edu"})

# Link text that carries no material identity on its own.
_GENERIC_LABELS = frozenset(
    {"", "download", "link", "here", "click here", "view", "open", "learning suite"}
)

_MATERIAL_TYPE = {
    SourceType.LEARNING_SUITE: "learning_suite_file",
    SourceType.BOX: "box_file",
    SourceType.YOUTUBE: "youtube_video",
    SourceType.DIRECT_DOCUMENT: "document",
    SourceType.EXTERNAL_WEB: "external_link",
}

_PLACEHOLDER_NAME = {
    SourceType.LEARNING_SUITE: "Learning Suite file",
    SourceType.BOX: "Box file",
    SourceType.YOUTUBE: "YouTube video",
    SourceType.DIRECT_DOCUMENT: "Document",
    SourceType.EXTERNAL_WEB: "External resource",
}


@dataclass(frozen=True)
class ContentPageObservation:
    """One captured content page's links (a recon snapshot's `links` list),
    plus the page URL and the course it belongs to."""

    links: Sequence[LinkRecord]
    page_url: str
    course_id: str
    observed_at: datetime | None = None


def build_manifest(
    observation: ContentPageObservation,
) -> list[MaterialManifestEntry]:
    """Pure, deterministic manifest for one content page.

    A link becomes a material iff it is a Learning Suite file download, or it
    is a cross-origin http(s) link to a non-chrome host. In-app navigation
    (same-origin, non-file) and site chrome are dropped. Entries are
    de-duplicated by identity (the `fileId` for a download, else a hash of the
    URL), first occurrence winning, page order preserved.
    """
    entries: list[MaterialManifestEntry] = []
    seen: set[str] = set()
    for link in observation.links:
        entry = _entry_from_link(link, observation)
        if entry is None or entry.id in seen:
            continue
        seen.add(entry.id)
        entries.append(entry)
    return entries


def _entry_from_link(
    link: LinkRecord, observation: ContentPageObservation
) -> MaterialManifestEntry | None:
    href = link.get("href")
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https"):
        return None

    is_file = _FILE_DOWNLOAD_PATH in parsed.path
    if not is_file:
        if link.get("same_origin"):
            return None
        if (link.get("domain") or "") in _CHROME_HOSTS:
            return None

    validated = _http_url(href)
    if validated is None:
        return None

    source_type = SourceType(link["source_type"])
    file_id = _file_id(parsed) if is_file else None
    identity = (
        f"{observation.course_id}:file:{file_id}"
        if file_id
        else f"{observation.course_id}:link:{_hash12(href)}"
    )
    return MaterialManifestEntry(
        id=identity,
        course_id=observation.course_id,
        name=_material_name(link, source_type),
        material_type=_MATERIAL_TYPE.get(source_type, "external_link"),
        status=AcquisitionStatus.DISCOVERED,
        source_url=validated,
        discovered_at=observation.observed_at,
    )


def _material_name(link: LinkRecord, source_type: SourceType) -> str:
    label = sanitize_label(link.get("text") or "")
    if (
        label
        and label.lower() not in _GENERIC_LABELS
        and not label.lower().startswith(("http://", "https://"))
    ):
        return label
    return _PLACEHOLDER_NAME.get(source_type, "External resource")


def _file_id(parsed) -> str | None:
    values = parse_qs(parsed.query).get("fileId")
    return values[0] if values else None


def _hash12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _http_url(value: str) -> HttpUrl | None:
    try:
        return _HTTP_URL.validate_python(value)
    except ValidationError:
        return None
