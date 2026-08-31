#!/usr/bin/env python3
"""Read-only Learning Suite Collector — automated assignment recon.

Where `recon_learning_suite.py` is a manual "navigate, press Enter to
capture" loop, this drives the navigation itself: after the human logs in,
it discovers every course from the course-switcher menu and captures each
course's assignments list, writing the same `recon-<ts>.json` that
`scripts/build_vault.py` consumes.

Guardrails (SECURITY.md, ARCHITECTURE §8.2 / §18.2 / §20.4):

- Read-only. The ONLY control it ever clicks is the course-switcher toggle
  (to reveal the course list). It never clicks Submit / Check off / any
  row control, never fills a form, never downloads.
- Authentication stays with the human. The tool never sees BYU / Duo
  credentials; it pauses and waits when it lands on a login wall.
- Hard budgets (max courses / pages / wall-clock) enforced in code.
- Scope is assignments only. Content / materials pages have no navigable
  in-app links yet (OBSERVATIONS.md) — use `recon_learning_suite.py` for
  those.

    uv run python scripts/collect_learning_suite.py
"""

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from scripts.recon_learning_suite import capture_page
from smartee.collector import (
    SNAPSHOT_ASSIGNMENTS_LIST,
    SNAPSHOT_NOT_LOGGED_IN,
    CollectionBudget,
    assignments_url,
    classify_snapshot,
    is_auth_wall,
    sleep_between_navigations,
)
from smartee.course.discovery import CourseMenuObservation, discover_courses

# The Course List page — carries the course-selection menu and, when it is
# open, the course entry links discovery reads.
DEFAULT_START_URL = "https://learningsuite.byu.edu/student/top"
DEFAULT_PROFILE_DIR = Path(".local/recon/browser-profile")
DEFAULT_OUTPUT_DIR = Path(".local/recon/output")

# The course-selection menu toggle (OBSERVATIONS.md / course/discovery.py).
_SWITCHER_TOGGLE = 'button[aria-label^="Show course selection menu" i]'
_NAV_TIMEOUT_MS = 45_000
_LS_HOST = "learningsuite.byu.edu"


def _settle(page: Page) -> None:
    """Let redirect chains and the SPA finish before reading `page.url`."""
    for state in ("load", "networkidle"):
        try:
            page.wait_for_load_state(state, timeout=8_000)
        except PlaywrightTimeout:
            pass


def _pick_page(context) -> Page:
    """Prefer a tab already on Learning Suite — a restored profile can reopen
    several, and the first is not always the live one."""
    for candidate in context.pages:
        if _LS_HOST in (candidate.url or ""):
            return candidate
    return context.pages[0] if context.pages else context.new_page()


# Structural containers Learning Suite always renders once the SPA has
# hydrated (OBSERVATIONS.md). `page.goto` returns on an empty shell, so we
# wait for one of these before capturing.
_CONTENT_READY = "#assignmentsComponent, #fullLSPage, #mainContent, h1, [role=button]"


def _await_content(page: Page) -> None:
    """Wait for the SPA to render real content, then a short grace for Vue to
    finish populating it."""
    try:
        page.wait_for_selector(_CONTENT_READY, timeout=15_000, state="attached")
    except PlaywrightTimeout:
        pass
    page.wait_for_timeout(1_500)


def _goto(page: Page, url: str) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
    except (PlaywrightError, PlaywrightTimeout):
        pass
    _settle(page)
    _await_content(page)


def _wait_for_login(page: Page, start_url: str) -> bool:
    """Pause for the human to authenticate. After each Enter, re-open the
    start page and let it settle before deciding. `skip` trusts the visible
    browser and proceeds anyway; `quit` aborts."""
    while True:
        _settle(page)
        if not is_auth_wall(page.url):
            return True
        print(f"\nLooks not-logged-in (script sees: {page.url.split('?')[0]}).")
        answer = (
            input(
                "Log in with BYU / Duo in the browser, then press Enter. "
                "('skip' if the browser already shows Learning Suite, 'quit' to stop): "
            )
            .strip()
            .lower()
        )
        if answer == "quit":
            return False
        if answer == "skip":
            _goto(page, start_url)
            return True
        _goto(page, start_url)


def _expand_course_switcher(page: Page) -> None:
    """Click the switcher toggle once so the course <a> entries render. This
    is the only click the Collector performs. If it does not work, the caller
    falls back to asking the human to open the menu."""
    try:
        toggle = page.query_selector(_SWITCHER_TOGGLE)
        if toggle is None:
            print("  (course-switcher toggle not found on this page)")
            return
        if (toggle.get_attribute("aria-expanded") or "").strip().lower() != "true":
            toggle.click()
            page.wait_for_timeout(1_000)
    except PlaywrightError as exc:
        print(f"  (could not expand the course switcher: {str(exc).splitlines()[0]})")


def _cid_link_count(snapshot: dict) -> int:
    return sum(
        1
        for e in snapshot["interactive_elements"]
        if e["tag"] == "a"
        and e.get("link")
        and "/student/cid-" in (e["link"].get("href") or "")
    )


def _discover_once(page: Page, debug_snapshots: list[dict]) -> list:
    """One discovery attempt. The raw capture is kept in `debug_snapshots` so
    a thin or empty result can be inspected after the run."""
    snapshot = capture_page(page)
    snapshot["collector_snapshot_kind"] = "course_menu"
    debug_snapshots.append(snapshot)
    result = discover_courses(
        CourseMenuObservation(
            elements=snapshot["interactive_elements"],
            menu_page_url=snapshot["url"],
            observed_at=datetime.now(UTC),
        )
    )
    print(
        f"  (menu page: {len(snapshot['interactive_elements'])} interactive, "
        f"{_cid_link_count(snapshot)} course links, "
        f"{len(result.courses)} discovered)"
    )
    return list(result.courses)


def _discover(
    page: Page, start_url: str, debug_snapshots: list[dict], *, allow_manual: bool
) -> list:
    """Discover courses from the course-selection menu. Tries an automatic
    toggle click first; falls back to asking the human to open the menu."""
    _expand_course_switcher(page)
    courses = _discover_once(page, debug_snapshots)
    if len(courses) > 1:
        return courses

    # Thin or empty — maybe we drifted off the Course List page, or the menu
    # needs a moment. Go back and try once more.
    _goto(page, start_url)
    _expand_course_switcher(page)
    retried = _discover_once(page, debug_snapshots)
    courses = retried if len(retried) >= len(courses) else courses
    if len(courses) > 1 or not allow_manual:
        return courses

    labels = sorted({b["label"] for b in capture_page(page)["buttons"]})
    print(
        f"\nOnly {len(courses)} course(s) found automatically.\n"
        f"Buttons seen on the page: {', '.join(labels) or '(none)'}\n"
        "Open the course menu manually in the browser so the full course list "
        "is visible, then press Enter (or 'quit' to go with what we have)."
    )
    if input("> ").strip().lower() == "quit":
        return courses
    manual = _discover_once(page, debug_snapshots)
    return manual if len(manual) >= len(courses) else courses


def _target_assignments_url(page: Page, entry_url: str) -> str | None:
    """The assignments-list URL for a course. Prefer deriving it from the
    switcher href; if that href is not course-scoped, navigate to it and
    derive from where the browser actually lands."""
    direct = assignments_url(entry_url)
    if direct is not None:
        return direct
    _goto(page, entry_url)
    return assignments_url(page.url)


def _capture_assignments(page: Page, url: str) -> dict | None:
    """Navigate to `url` and capture it, with one reload retry if the first
    capture is not an assignments list (same-URL-different-DOM)."""
    for attempt in (1, 2):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
        except PlaywrightTimeout:
            pass
        except PlaywrightError as exc:
            print(f"  (navigation failed: {str(exc).splitlines()[0]})")
            return None
        _settle(page)
        _await_content(page)
        sleep_between_navigations()
        try:
            snapshot = capture_page(page)
        except (PlaywrightError, RuntimeError) as exc:
            print(f"  (capture failed: {str(exc).splitlines()[0]})")
            return None
        kind = classify_snapshot(snapshot)
        if kind in (SNAPSHOT_ASSIGNMENTS_LIST, SNAPSHOT_NOT_LOGGED_IN) or attempt == 2:
            snapshot["collector_snapshot_kind"] = kind
            return snapshot
        print(f"  (got '{kind}', retrying once)")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-url", default=DEFAULT_START_URL)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-courses", type=int, default=None)
    parser.add_argument("--nav-delay", type=float, default=None)
    args = parser.parse_args()

    budget = CollectionBudget(
        **{
            k: v
            for k, v in (
                ("max_courses", args.max_courses),
                ("nav_delay_seconds", args.nav_delay),
            )
            if v is not None
        }
    )

    args.profile_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = (
        args.output_dir / f"recon-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    snapshots: list[dict] = []

    def persist() -> None:
        if snapshots:
            out_path.write_text(json.dumps(snapshots, indent=2))

    start = time.monotonic()
    deadline = budget.deadline_from(start)
    courses_done = 0
    lists_captured = 0

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(args.profile_dir), headless=False
        )
        page = _pick_page(context)
        try:
            page.bring_to_front()
        except PlaywrightError:
            pass

        print("READ-ONLY Collector. Clicks only the course-switcher toggle.")
        _goto(page, args.start_url)

        if not _wait_for_login(page, args.start_url):
            print("Aborted before login.")
            context.close()
            return

        courses = _discover(page, args.start_url, snapshots, allow_manual=True)
        persist()
        if not courses:
            print(
                "No courses discovered from the switcher menu. "
                f"Menu snapshot(s) saved to {out_path} for analysis."
            )
            context.close()
            return
        print(f"Discovered {len(courses)} course(s).")

        for course in courses:
            stop = budget.exhausted(
                pages=len(snapshots),
                courses=courses_done,
                now=time.monotonic(),
                deadline=deadline,
            )
            if stop:
                print(f"Stopping: {stop}.")
                break

            print(f"- {course.label}")
            target = _target_assignments_url(page, course.entry_url)
            if target is None:
                print("  (no course-scoped URL; skipped)")
                courses_done += 1
                continue

            snapshot = _capture_assignments(page, target)
            courses_done += 1
            if snapshot is None:
                continue
            snapshots.append(snapshot)
            persist()

            kind = snapshot.get("collector_snapshot_kind")
            if kind == SNAPSHOT_NOT_LOGGED_IN:
                print("  Session lost mid-run. Stopping and saving what we have.")
                break
            if kind == SNAPSHOT_ASSIGNMENTS_LIST:
                lists_captured += 1
                rows = len(snapshot.get("assignment_row_candidates", []))
                print(f"  captured assignments list ({rows} row candidates)")
            else:
                print(f"  captured '{kind}' (kept for analysis)")

        context.close()

    persist()
    print(
        f"\nDone. {courses_done} course(s) visited, "
        f"{lists_captured} assignments list(s) captured, "
        f"{len(snapshots)} snapshot(s) -> {out_path if snapshots else '(nothing saved)'}"
    )


if __name__ == "__main__":
    main()
