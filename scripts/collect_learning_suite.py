#!/usr/bin/env python3
"""Read-only Learning Suite Collector — automated assignment recon.

Where `recon_learning_suite.py` is a manual "navigate, press Enter to
capture" loop, this drives the navigation itself: after the human logs in,
it discovers every course from the course-switcher menu and captures each
course's assignments list, writing the same `recon-<ts>.json` that
`scripts/build_vault.py` consumes.

Guardrails (SECURITY.md, ARCHITECTURE §8.2 / §18.2 / §20.4, D-023):

- Read-only. The only elements it ever clicks are the course-switcher
  toggle and a course entry inside that menu (`<a href*="cid-<id>">`) — the
  reliable way to move the SPA between courses, since a bare URL `goto`
  does not switch the assignments view. It never clicks Submit / Check off
  / any row or detail control, never fills a form, never downloads.
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
import re
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
    assignments_url_from_session,
    classify_snapshot,
    is_auth_wall,
    sleep_between_navigations,
)
from smartee.course.discovery import (
    CourseMenuObservation,
    DiscoveredCourse,
    discover_courses,
)

# Learning Suite shows the active course as
# `… Current course: <label>` on the switcher toggle's aria-label.
_CURRENT_COURSE_PREFIX = "current course: "
# Leading course-code token of a label ("CYBER 467 (001) - …" → "CYBER 467"),
# used to match a discovery label against the switcher's current-course text
# when the two render the surrounding detail differently.
_COURSE_CODE_RE = re.compile(r"^([A-Za-z][A-Za-z&]*(?:\s+[A-Za-z&]+)*\s+\d{2,4})")

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
    """Click the switcher toggle so the course <a> entries render. If it does
    not work, the caller falls back to asking the human to open the menu."""
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


def _course_code(label: str) -> str:
    """The leading course-code token of a label, lowercased ("CYBER 467 (001)
    - …" → "cyber 467"). Empty when the label has no recognisable code."""
    match = _COURSE_CODE_RE.match(label.strip())
    return (match.group(1) if match else "").strip().lower()


def _current_course_label(page: Page) -> str:
    """What the switcher toggle says the active course is, or ''."""
    try:
        toggle = page.query_selector(_SWITCHER_TOGGLE)
        aria = (toggle.get_attribute("aria-label") or "") if toggle else ""
    except PlaywrightError:
        return ""
    lowered = aria.lower()
    marker = lowered.find(_CURRENT_COURSE_PREFIX)
    return aria[marker + len(_CURRENT_COURSE_PREFIX) :].strip() if marker >= 0 else ""


def _on_course(page: Page, course: DiscoveredCourse) -> bool:
    """True when the switcher shows `course` as the current course."""
    code = _course_code(course.label)
    return bool(code) and code in _current_course_label(page).lower()


def _switch_to_course(page: Page, course: DiscoveredCourse) -> bool:
    """Move the SPA to `course` by clicking its entry in the course-switcher
    menu. A bare URL `goto` does not switch the assignments view (the URL
    `cid-` token is not authoritative — SESSION_STATE / OBSERVATIONS.md), so
    the menu click is the reliable path. The only elements this ever clicks
    are the switcher toggle and a course-scoped `<a href*="cid-<id>">` — never
    a submission or row control (SECURITY.md, D-023)."""
    selector = f'a[href*="cid-{course.course_id}"]'
    for attempt in (1, 2):
        _expand_course_switcher(page)
        entry = page.query_selector(selector)
        if entry is None:
            print(f"  (no switcher entry for {course.label!r})")
            return False
        try:
            entry.click()
        except PlaywrightError as exc:
            print(f"  (could not click course entry: {str(exc).splitlines()[0]})")
            return False
        _settle(page)
        _await_content(page)
        sleep_between_navigations()
        if _on_course(page, course) or attempt == 2:
            break
    return _on_course(page, course)


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


def _capture_here(page: Page) -> dict | None:
    """Snapshot the current page, tolerating a transient DOM error."""
    _settle(page)
    _await_content(page)
    sleep_between_navigations()
    try:
        return capture_page(page)
    except (PlaywrightError, RuntimeError) as exc:
        print(f"  (capture failed: {str(exc).splitlines()[0]})")
        return None


def _goto_assignments_tab(page: Page, course: DiscoveredCourse) -> None:
    """Once the SPA is on the course, make sure we are on its assignments
    view. The course home already renders the assignments list, but the
    explicit sub-URL is steadier; derive it from the live session URL +
    course id, never from the unreliable switcher href."""
    target = assignments_url_from_session(page.url, course.course_id)
    if target and target.split("?")[0] != page.url.split("?")[0]:
        _goto(page, target)


def _collect_course(page: Page, course: DiscoveredCourse) -> dict | None:
    """Switch to `course` via the menu, land on its assignments list, capture.
    The snapshot is tagged with the course discovery identified so attribution
    never depends on re-reading the (lagging) switcher label later."""
    switched = _switch_to_course(page, course)
    if not switched:
        print("  (switcher did not confirm the course; capturing anyway)")
    _goto_assignments_tab(page, course)

    snapshot = _capture_here(page)
    if snapshot is None:
        return None
    if not snapshot.get("assignment_row_candidates") and switched:
        # One reopen — the list sometimes paints a beat after the shell.
        _switch_to_course(page, course)
        _goto_assignments_tab(page, course)
        snapshot = _capture_here(page) or snapshot

    snapshot["collector_course_id"] = course.course_id
    snapshot["collector_course_label"] = course.label
    snapshot["collector_course_confirmed"] = _on_course(page, course)
    snapshot["collector_snapshot_kind"] = classify_snapshot(snapshot)
    return snapshot


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
            snapshot = _collect_course(page, course)
            courses_done += 1
            if snapshot is None:
                continue
            snapshots.append(snapshot)
            persist()

            kind = snapshot.get("collector_snapshot_kind")
            confirmed = "" if snapshot.get("collector_course_confirmed") else " (unconfirmed)"
            if kind == SNAPSHOT_NOT_LOGGED_IN:
                print("  Session lost mid-run. Stopping and saving what we have.")
                break
            if kind == SNAPSHOT_ASSIGNMENTS_LIST:
                lists_captured += 1
                rows = len(snapshot.get("assignment_row_candidates", []))
                print(f"  captured assignments list ({rows} row candidates){confirmed}")
            else:
                print(f"  captured '{kind}' (kept for analysis){confirmed}")

        context.close()

    persist()
    print(
        f"\nDone. {courses_done} course(s) visited, "
        f"{lists_captured} assignments list(s) captured, "
        f"{len(snapshots)} snapshot(s) -> {out_path if snapshots else '(nothing saved)'}"
    )


if __name__ == "__main__":
    main()
