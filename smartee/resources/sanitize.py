import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ALLOWED_SCHEMES = {"http", "https"}

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# Same, but keeps newline (\x0a) and tab (\x09) so a multi-line block survives.
_CONTROL_CHARS_KEEP_BREAKS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_BLANK_LINE_RUN = re.compile(r"\n\s*\n(\s*\n)+")
_LABEL_MAX_LENGTH = 200
_TEXT_BLOCK_MAX_LENGTH = 4000

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
_SENSITIVE_ATTR_TERMS = (
    *_SENSITIVE_QUERY_KEY_SUBSTRINGS,
    "bearer",
    "oauth",
    "saml",
    "cookie",
    "csrf",
    "nonce",
    "duo",
)

# Split an identifier into tokens on camelCase, digit, and separator boundaries
# ("data-assignment-id" -> assignment/id; "csrfToken" -> csrf/token;
# "OAuth2" -> o/auth/2) so sensitive-term matching happens per token, not on
# raw substrings ("sig" inside "assignment" must not match).
_IDENT_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def looks_sensitive(text: str) -> bool:
    """True if `text` (an attribute name or value) has a *token* that is, starts
    with, or ends with a credential/session/auth term.

    Token/boundary aware: `text` is first split on camelCase / digit / separator
    boundaries, so a term only matches at a token edge. "authToken", "X-CSRF",
    "signature", and a bare "jwt" are flagged; "assignment" and
    "data-assignment-id" (which merely contain "sig") are not.

    Deterministic, no network. URL query-key sanitization is unaffected — it
    uses `_is_sensitive_query_key`, not this function.
    """
    tokens = [match.group().lower() for match in _IDENT_TOKEN_RE.finditer(text)]
    return any(
        token.startswith(term) or token.endswith(term)
        for token in tokens
        for term in _SENSITIVE_ATTR_TERMS
    )


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


def sanitize_text_block(text: str, *, max_length: int = _TEXT_BLOCK_MAX_LENGTH) -> str:
    """Multi-line variant of `sanitize_label` for a block of untrusted
    course-authored text (e.g. an assignment description).

    Keeps line breaks (so structure survives) but strips every other control
    character, trims each line, collapses runs of blank lines to one, and caps
    total length. Like `sanitize_label` this is safe for logs / local JSON
    output but is NOT sufficient sanitization for prompt context.
    """
    lines = [
        " ".join(_CONTROL_CHARS_KEEP_BREAKS.sub(" ", line).split())
        for line in text.splitlines()
    ]
    cleaned = _BLANK_LINE_RUN.sub("\n\n", "\n".join(lines).strip())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "…"
    return cleaned


def domain_of(url: str) -> str | None:
    """Extract the lowercase hostname from a URL, or None if it has none."""
    try:
        hostname = urlparse(url).hostname
    except ValueError:
        return None
    return hostname.lower() if hostname else None


def is_same_origin(url: str, reference_url: str) -> bool:
    return domain_of(url) is not None and domain_of(url) == domain_of(reference_url)
