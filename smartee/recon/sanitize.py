from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ALLOWED_SCHEMES = {"http", "https"}

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


def domain_of(url: str) -> str | None:
    """Extract the lowercase hostname from a URL, or None if it has none."""
    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return None
    return hostname.lower() if hostname else None


def is_same_origin(url: str, reference_url: str) -> bool:
    return domain_of(url) is not None and domain_of(url) == domain_of(reference_url)
