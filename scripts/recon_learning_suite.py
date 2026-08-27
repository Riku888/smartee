#!/usr/bin/env python3
"""Read-only Learning Suite reconnaissance tool.

Launches headful Chromium with a local persistent profile, lets the user
log in manually (BYU auth / Duo — this tool never sees those credentials),
and on request captures a sanitized snapshot of the current page's visible
structure (URL, title, headings, links, buttons, and a generic
read-only capture of interactive elements' structural attributes).

This tool never clicks, submits, checks off, or fills anything. It only
reads DOM text/attributes. See SECURITY.md and CLAUDE.md Hard Rules.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import Page, sync_playwright

from smartee.resources import (
    INTERACTIVE_SELECTOR,
    SAFE_ATTRIBUTE_NAMES,
    build_interactive_element_record,
    build_link_record,
    sanitize_url,
)

DEFAULT_START_URL = "https://learningsuite.byu.edu/"
DEFAULT_PROFILE_DIR = Path(".local/recon/browser-profile")
DEFAULT_OUTPUT_DIR = Path(".local/recon/output")

HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6"
BUTTON_SELECTOR = "button, input[type=submit], input[type=button], [role=button]"

# Read every attribute name/value pair from an element without executing
# anything. Used only to split out data-* names for the interactive capture.
_ELEMENT_ATTRS_JS = (
    "e => Object.fromEntries(Array.from(e.attributes, a => [a.name, a.value]))"
)


def capture_page(page: Page) -> dict:
    """Read-only DOM snapshot of the current page. No clicks, no form fills."""
    current_url = page.url

    headings = [
        {"level": el.evaluate("e => e.tagName.toLowerCase()"), "text": text}
        for el in page.query_selector_all(HEADING_SELECTOR)
        if (text := el.inner_text().strip())
    ]

    links = [
        build_link_record(a.inner_text(), a.get_attribute("href") or "", current_url)
        for a in page.query_selector_all("a[href]")
    ]

    buttons = [
        {
            "label": label,
            "tag": b.evaluate("e => e.tagName.toLowerCase()"),
        }
        for b in page.query_selector_all(BUTTON_SELECTOR)
        if (label := (b.inner_text() or b.get_attribute("value") or "").strip())
    ]

    interactive_elements = [
        _capture_interactive_element(el, current_url)
        for el in page.query_selector_all(INTERACTIVE_SELECTOR)
    ]

    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "url": sanitize_url(current_url) or "UNKNOWN",
        "title": page.title(),
        "headings": headings,
        "links": links,
        "buttons": buttons,
        "interactive_elements": interactive_elements,
    }


def _capture_interactive_element(el, current_url: str) -> dict:
    """Read-only structural snapshot of one interactive element (`a`, `button`,
    `[role=button]`). Reads attribute text only — no click, no handler run.

    Sanitization (inert labels, credential/session redaction, onclick reduced to
    a local-only representation) lives in `build_interactive_element_record`.
    data-* values live only in this local, gitignored output.
    """
    raw_attrs = el.evaluate(_ELEMENT_ATTRS_JS)
    tag = el.evaluate("e => e.tagName.toLowerCase()")
    label = (el.inner_text() or el.get_attribute("value") or "").strip()

    attributes = {
        name: raw_attrs.get(name)
        for name in (*SAFE_ATTRIBUTE_NAMES, "href")
        if name in raw_attrs
    }
    data_attributes = {
        name: value for name, value in raw_attrs.items() if name.startswith("data-")
    }

    record = build_interactive_element_record(
        tag,
        label,
        current_url,
        attributes=attributes,
        data_attributes=data_attributes,
        onclick=raw_attrs.get("onclick"),
    )
    return dict(record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-url", default=DEFAULT_START_URL)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    args.profile_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    snapshots: list[dict] = []

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(args.profile_dir), headless=False
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(args.start_url)

        print("READ-ONLY recon session.")
        print("This tool never submits, checks off, or clicks state-changing controls.")
        print(
            "Log in manually (BYU / Duo) and navigate to the page you want to capture."
        )
        print("Commands: [Enter] capture current page, 'quit' to finish and save.\n")

        while True:
            command = input("> ").strip().lower()
            if command == "quit":
                break
            snapshot = capture_page(page)
            snapshots.append(snapshot)
            print(
                f"Captured: {snapshot['url']} "
                f"({len(snapshot['links'])} links, {len(snapshot['buttons'])} buttons, "
                f"{len(snapshot['interactive_elements'])} interactive elements)"
            )

        context.close()

    if not snapshots:
        print("No snapshots captured; nothing saved.")
        return

    out_path = (
        args.output_dir / f"recon-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out_path.write_text(json.dumps(snapshots, indent=2))
    print(f"Saved {len(snapshots)} snapshot(s) to {out_path}")


if __name__ == "__main__":
    main()
