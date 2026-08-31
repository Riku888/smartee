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

# The course-scoped prefix of an in-course URL path, e.g. the
# `/.MjTJ/student/cid--tQDtJf5AeQC` of
# `/.MjTJ/student/cid--tQDtJf5AeQC/student/home/dashboard`. The opaque token
# after `cid-` is the durable course id (`smartee/course/discovery.py`).
_COURSE_PREFIX_RE = re.compile(r"^(?P<prefix>.*?/student/cid-[A-Za-z0-9_-]+)(?:/|$)")

# VERIFIED tail for a course's assignments list — observed directly at
# `student/home` and `student/home/assignments` for a current-term course,
# and present verbatim in some course-switcher hrefs (OBSERVATIONS.md).
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


def assignments_url(in_course_url: str) -> str | None:
    """The assignments-list URL for the course `in_course_url` belongs to.

    Takes the course-scoped prefix of a URL the browser actually resolved to
    (`…/student/cid-<id>`) and appends the verified `student/home/assignments`
    tail, keeping the original scheme and host. Returns None when the URL has
    no `/student/cid-<id>/` segment — the caller then skips that course
    rather than guessing.
    """
    try:
        parsed = urlparse(in_course_url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    match = _COURSE_PREFIX_RE.match(parsed.path)
    if match is None:
        return None
    path = f"{match.group('prefix')}/{_ASSIGNMENTS_TAIL}"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


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
