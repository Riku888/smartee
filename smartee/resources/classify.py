from urllib.parse import urlparse

from smartee.domain.enums import SourceType

_LEARNING_SUITE_HOST = "learningsuite.byu.edu"
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_DIRECT_DOCUMENT_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".zip",
)


def classify_source_type(href: str) -> SourceType:
    """Classify a link's destination from its URL alone. No page content is inspected."""
    try:
        parsed = urlparse(href)
    except ValueError:
        return SourceType.UNKNOWN

    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return SourceType.UNKNOWN

    host = parsed.hostname.lower()

    if host == _LEARNING_SUITE_HOST or host.endswith(f".{_LEARNING_SUITE_HOST}"):
        return SourceType.LEARNING_SUITE
    if host == "box.com" or host.endswith(".box.com"):
        return SourceType.BOX
    if host in _YOUTUBE_HOSTS:
        return SourceType.YOUTUBE
    if parsed.path.lower().endswith(_DIRECT_DOCUMENT_EXTENSIONS):
        return SourceType.DIRECT_DOCUMENT
    return SourceType.EXTERNAL_WEB
