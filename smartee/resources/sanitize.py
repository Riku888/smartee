import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ALLOWED_SCHEMES = {"http", "https"}

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_LABEL_MAX_LENGTH = 200

_SENSITIVE_QUERY_KEY_SUBSTRINGS = (
    "token",
    "session",
    "auth",
    "key",
    "secret",
    "password",
    "pwd",
    "ticket",
    "sig",
    "jwt",
    "cred",
)

# SSO/CAS/SAML login flows (observed: cas.byu.edu) carry auth-flow state
# (RelayState, srid, entityId, service, ...) in query params that don't
# contain any of the substrings above. Rather than chase an open-ended list
# of provider-specific param names, treat the entire query string on these
# hosts/paths as sensitive and drop it outright.
_SSO_HOST_SUBSTRINGS = (
    "cas.byu.edu",
    "okta.com",
    "duosecurity.com",
    "duofederal.com",
)
_SSO_PATH_SUBSTRINGS = (
    "/cas/",
    "/saml",
    "/idp/",
    "/sso",
)


def _is_sensitive_query_key(key: str) -> bool:
    lowered = key.lower()
    return any(substring in lowered for substring in _SENSITIVE_QUERY_KEY_SUBSTRINGS)


# Extra terms that mark an attribute NAME or VALUE as credential/session/auth
# related when captured from arbitrary DOM elements (recon attribute capture).
# Kept separate from the URL query-key list above so URL sanitization behavior
# is unchanged.
_SENSITIVE_ATTR_SUBSTRINGS = (
    *_SENSITIVE_QUERY_KEY_SUBSTRINGS,
    "bearer",
    "oauth",
    "saml",
    "cookie",
    "csrf",
    "nonce",
    "duo",
)


def looks_sensitive(text: str) -> bool:
    """True if `text` (an attribute name or value) contains a token that looks
    credential/session/auth/token related.

    Deterministic substring match, no network or inference. Used to redact
    attribute captures before they are written to the local recon output.
    """
    lowered = text.lower()
    return any(substring in lowered for substring in _SENSITIVE_ATTR_SUBSTRINGS)


def _is_sso_url(parsed) -> bool:
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    return any(substring in host for substring in _SSO_HOST_SUBSTRINGS) or any(
        substring in path for substring in _SSO_PATH_SUBSTRINGS
    )


def sanitize_url(raw: str) -> str | None:
    """Strip fragments and likely-sensitive query params from a URL.

    Returns None for non-http(s) schemes (mailto:, javascript:, data:, etc.)
    or unparseable input, so nothing session/credential-like can leak into
    recon output. This is the single source of truth for any URL that
    reaches console output or JSON output — callers must never print a raw
    URL and must never diverge between the two.
    """
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None

    if parsed.scheme.lower() not in ALLOWED_SCHEMES or not parsed.netloc:
        return None

    if _is_sso_url(parsed):
        return urlunparse(parsed._replace(query="", fragment=""))

    safe_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_sensitive_query_key(key)
    ]

    return urlunparse(parsed._replace(query=urlencode(safe_query), fragment=""))


def sanitize_label(text: str, *, max_length: int = _LABEL_MAX_LENGTH) -> str:
    """Reduce untrusted anchor/link text to an inert one-line label.

    Course-authored text is untrusted (Hard Rule 6, prompt-injection risk) and
    can be personally identifying. Control characters are dropped, whitespace is
    collapsed, and the result is length-capped so it is safe to place in logs or
    JSON output. This is NOT sufficient sanitization for prompt context.
    """
    collapsed = " ".join(_CONTROL_CHARS.sub(" ", text).split())
    if len(collapsed) > max_length:
        collapsed = collapsed[:max_length].rstrip() + "…"
    return collapsed


def domain_of(url: str) -> str | None:
    """Extract the lowercase hostname from a URL, or None if it has none."""
    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return None
    return hostname.lower() if hostname else None


def is_same_origin(url: str, reference_url: str) -> bool:
    return domain_of(url) is not None and domain_of(url) == domain_of(reference_url)
