"""Deterministic decisions for a read-only Collector pass over Learning Suite.

`scripts/collect_learning_suite.py` drives Playwright; the choices it makes
between navigations live here so they can be unit-tested without a browser:
where to go for a course's assignments list, and what a captured page
turned out to be.

No network, no Playwright, no LLM. Everything here operates on strings and
already-captured snapshot dicts.

Scope is deliberately narrow (assignments only). Content / materials pages
are not navigable deterministically yet — their in-app section links carry
no href (`docs/recon/OBSERVATIONS.md`) — so the Collector does not attempt
them, and manual recon stays the path for materials.
"""

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

# The session path token Learning Suite puts right after the host, e.g. the
# `.RENB` of `/.RENB/cid-<id>/student/home/assignments`. Stable within one
# login session, rotates between sessions. Optional — an unauthenticated or
# pre-redirect URL has none.
_SESSION_TOKEN_RE = re.compile(r"^/(\.[A-Za-z0-9_-]+)(?=/)")

# The course id segment, `/cid-<opaque token>`. The token after `cid-` is the
# durable course id (`smartee/course/discovery.py`). Learning Suite sometimes
# renders course-switcher hrefs with a spurious `/student` before it
# (`/.RENB/student/cid-<id>/...`); the URL it actually serves has none
# (`/.RENB/cid-<id>/student/home/assignments`, verified 2026-09-04).
_CID_RE = re.compile(r"/cid-([A-Za-z0-9_-]+)")

# VERIFIED tail for a course's assignments list — observed directly at
# `student/home` and `student/home/assignments` for a current-term course
# (OBSERVATIONS.md).
_ASSIGNMENTS_TAIL = "student/home/assignments"

# Hosts that mean "the session is gone, a human must log in" — never a page
# to parse. CAS is Learning Suite's unauthenticated entry point
# (`cas.byu.edu`, federated to Okta); a bare Learning Suite host with a
# `/cas/login` path is the same signal.
_AUTH_WALL_HOSTS = ("cas.byu.edu", "okta.com", "login.byu.edu")

SNAPSHOT_ASSIGNMENTS_LIST = "assignments_list"
SNAPSHOT_EXAM_LIST = "exam_list"
SNAPSHOT_NOT_LOGGED_IN = "not_logged_in"
SNAPSHOT_OTHER = "other"


@dataclass(frozen=True)
class CollectionBudget:
    """Hard limits enforced by the Collector outside any model (D-019 /
    ARCHITECTURE §20.4). Conservative by default — this is a read-only pass
    over a live authenticated site."""

    max_courses: int = 20
    max_pages: int = 60
    max_seconds: float = 900.0
    nav_delay_seconds: float = 2.0

    def deadline_from(self, start: float) -> float:
        """Absolute `time.monotonic()` value at which the pass must stop."""
        return start + self.max_seconds

    def exhausted(
        self, *, pages: int, courses: int, now: float, deadline: float
    ) -> str | None:
        """A short reason string if any limit is hit, else None."""
        if pages >= self.max_pages:
            return f"page budget reached ({self.max_pages})"
        if courses >= self.max_courses:
            return f"course budget reached ({self.max_courses})"
        if now >= deadline:
            return f"time budget reached ({self.max_seconds:.0f}s)"
        return None


DEFAULT_BUDGET = CollectionBudget()


def is_auth_wall(url: str) -> bool:
    """True when `url` is a login redirect, not a Learning Suite page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in _AUTH_WALL_HOSTS):
        return True
    return "/cas/login" in parsed.path


def _compose_assignments_url(
    scheme: str, netloc: str, token: str | None, course_id: str
) -> str:
    """Build the canonical `/.<token>/cid-<id>/student/home/assignments` URL —
    no `/student` before `cid-` (verified 2026-09-04)."""
    token_segment = f"/{token}" if token else ""
    cid = course_id if course_id.startswith("cid-") else f"cid-{course_id}"
    path = f"{token_segment}/{cid}/{_ASSIGNMENTS_TAIL}"
    return urlunparse((scheme, netloc, path, "", "", ""))


def assignments_url(in_course_url: str) -> str | None:
    """The assignments-list URL for the course `in_course_url` belongs to.

    Reads the session token (if any) and the `/cid-<id>` segment from a URL
    the browser resolved to, and rebuilds the canonical
    `/.<token>/cid-<id>/student/home/assignments` — normalising away any
    spurious `/student` Learning Suite renders before `/cid-` in switcher
    hrefs. Returns None when the URL is a login wall or carries no
    `/cid-<id>` segment, so the caller skips that course rather than guessing.
    """
    try:
        parsed = urlparse(in_course_url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname or is_auth_wall(in_course_url):
        return None
    cid_match = _CID_RE.search(parsed.path)
    if cid_match is None:
        return None
    token_match = _SESSION_TOKEN_RE.match(parsed.path)
    return _compose_assignments_url(
        parsed.scheme,
        parsed.netloc,
        token_match.group(1) if token_match else None,
        cid_match.group(1),
    )


def assignments_url_from_session(session_url: str, course_id: str) -> str | None:
    """Compose a course's assignments-list URL from any authenticated Learning
    Suite URL (for its scheme / host / session token) plus a `course_id` from
    discovery. The most reliable derivation — discovery's `course_id` is the
    durable `cid-` token and the session URL carries the current token.
    Returns None if `session_url` is unusable or a login wall.
    """
    try:
        parsed = urlparse(session_url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname or is_auth_wall(session_url):
        return None
    if not course_id:
        return None
    token_match = _SESSION_TOKEN_RE.match(parsed.path)
    return _compose_assignments_url(
        parsed.scheme,
        parsed.netloc,
        token_match.group(1) if token_match else None,
        course_id,
    )


def classify_snapshot(snapshot: Mapping[str, object]) -> str:
    """What a captured page turned out to be — the same URL can render an
    assignments list, an Exam List, or something else entirely
    (OBSERVATIONS.md, "same URL, different DOM"), so the Collector checks the
    capture, not the URL it asked for."""
    url = snapshot.get("url")
    if isinstance(url, str) and is_auth_wall(url):
        return SNAPSHOT_NOT_LOGGED_IN
    if snapshot.get("assignments_component_present"):
        return SNAPSHOT_ASSIGNMENTS_LIST
    candidates = snapshot.get("assignment_row_candidates")
    if isinstance(candidates, list) and candidates:
        return SNAPSHOT_ASSIGNMENTS_LIST
    headings = snapshot.get("headings")
    if isinstance(headings, list):
        for heading in headings:
            text = heading.get("text", "") if isinstance(heading, Mapping) else ""
            if isinstance(text, str) and text.strip().lower() == "exam list":
                return SNAPSHOT_EXAM_LIST
    return SNAPSHOT_OTHER


def sleep_between_navigations(budget: CollectionBudget = DEFAULT_BUDGET) -> None:
    """Politeness delay between page loads. Isolated so tests can monkeypatch
    it and the Collector has one place to be courteous to the server."""
    if budget.nav_delay_seconds > 0:
        time.sleep(budget.nav_delay_seconds)
