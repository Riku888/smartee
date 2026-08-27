from typing import TypedDict
from urllib.parse import urljoin

from smartee.resources.classify import classify_source_type
from smartee.resources.sanitize import domain_of, is_same_origin, sanitize_url


class LinkRecord(TypedDict):
    text: str
    href: str | None
    domain: str | None
    source_type: str
    same_origin: bool


def build_link_record(text: str, href: str, current_url: str) -> LinkRecord:
    """Pure, deterministic transform from a raw (text, href) anchor pair to a
    sanitized record. Never inspects or invents page structure — the caller
    supplies whatever the DOM actually returned.

    `href` is resolved against `current_url` via standard URL resolution
    (`urljoin`) before classification/sanitization, so relative in-app
    links (e.g. `/course/pages/id-123`) are recognized as Learning Suite
    URLs instead of falling through to `unknown`. Non-http(s) schemes
    (`mailto:`, `javascript:`, ...) are absolute already, so `urljoin`
    passes them through unchanged and they're still rejected downstream.
    """
    resolved_href = urljoin(current_url, href)
    return LinkRecord(
        text=text.strip(),
        href=sanitize_url(resolved_href),
        domain=domain_of(resolved_href),
        source_type=classify_source_type(resolved_href).value,
        same_origin=is_same_origin(resolved_href, current_url),
    )
