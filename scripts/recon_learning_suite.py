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
    InteractiveElementRecord,
    build_container_record,
    build_interactive_element_record,
    build_link_record,
    build_node_record,
    sanitize_label,
    sanitize_text_block,
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

# Visible action/status labels observed VERIFIED on real assignments-list rows
# (docs/recon/OBSERVATIONS.md). Used only to locate candidate row containers to
# capture for later human analysis — NOT a production selector contract, and no
# control is ever clicked.
ASSIGNMENT_ACTION_LABELS = frozenset(
    {"submit", "view", "view/submit", "completed", "closed", "feedback", "check off"}
)
ROW_ANCESTOR_LEVELS = 4
# One real course exposed 26 assignment rows (9 Closed + 17 Completed); the old
# cap of 12 silently dropped the rest. Kept as a generous upper bound so one
# snapshot's capture still cannot approach a full-DOM dump.
MAX_ASSIGNMENT_ROWS = 150

# The assignments-list view is rendered inside this element; the Exam List view
# that can appear at the same URL is not (docs/recon/OBSERVATIONS.md).
ASSIGNMENTS_COMPONENT_SELECTOR = "#assignmentsComponent"

# When an assignment row is expanded, its description body lives here — deeper
# than the bounded descendant walk reaches, so it is captured directly (read
# only, `.inner_text()`) and passed through `sanitize_text_block` (untrusted
# course-authored text, Hard Rule 6). Local `.local/` evidence only.
DESCRIPTION_BLOCK_SELECTOR = "#AssignmentDescription, #descriptionBlock"

# Read-only bounded walk of an element's descendant *elements*: tag, a short
# structural path, direct text-node text, class, and raw attributes. Reads only
# Element attributes and text nodes — never a value/property, never a handler.
_DESCENDANT_WALK_JS = """
el => {
  const MAX = 90, MAX_DEPTH = 6;
  const SKIP = new Set(
    ['script', 'style', 'svg', 'input', 'textarea', 'select', 'option']
  );
  const out = [];
  const walk = (node, path, depth) => {
    if (depth > MAX_DEPTH) return;
    const kids = node.children;
    for (let i = 0; i < kids.length && out.length < MAX; i++) {
      const c = kids[i];
      const tag = c.tagName.toLowerCase();
      const p = path + '/' + tag + '[' + (i + 1) + ']';
      if (SKIP.has(tag)) continue;
      let t = '';
      for (const n of c.childNodes) { if (n.nodeType === 3) t += n.textContent + ' '; }
      out.push({
        tag: tag,
        path: p,
        text: t.trim(),
        class: c.getAttribute('class') || '',
        attrs: Object.fromEntries(Array.from(c.attributes, a => [a.name, a.value])),
      });
      walk(c, p, depth + 1);
    }
  };
  walk(el, '', 0);
  return out;
}
"""


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
        "assignments_component_present": page.query_selector(
            ASSIGNMENTS_COMPONENT_SELECTOR
        )
        is not None,
        "assignment_row_candidates": _assignment_row_candidates(page, current_url),
        "assignment_detail_candidate": _assignment_detail_candidate(page, current_url),
    }


def _norm_label(text: str) -> str:
    return " ".join(text.split()).lower()


def _parent_element(el):
    """Parent element handle, or None. Reads `parentElement` only — no handler."""
    return el.evaluate_handle("e => e.parentElement").as_element()


def _ancestor_chain(el, levels: int) -> list:
    """Up to `levels` ancestor element handles, innermost first."""
    chain = []
    current = el
    for _ in range(levels):
        parent = _parent_element(current)
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return chain


def _capture_node(el) -> dict:
    """Cheap structural record for one element: tag / class / safe attributes."""
    raw_attrs = el.evaluate(_ELEMENT_ATTRS_JS)
    tag = el.evaluate("e => e.tagName.toLowerCase()")
    return dict(
        build_node_record(
            tag,
            raw_attrs.get("class"),
            attributes=raw_attrs,
            data_attributes=raw_attrs,
        )
    )


def _capture_container(el, current_url: str) -> dict:
    """Bounded structural record for one candidate row/detail container: its own
    attributes, its descendant elements' tag/path/text, plus links and
    interactive controls routed through the shared sanitized builders. No
    handler is executed; sanitization/capping lives in `build_container_record`.
    """
    raw_attrs = el.evaluate(_ELEMENT_ATTRS_JS)
    node = build_node_record(
        el.evaluate("e => e.tagName.toLowerCase()"),
        raw_attrs.get("class"),
        attributes=raw_attrs,
        data_attributes=raw_attrs,
    )
    links = [
        build_link_record(a.inner_text(), a.get_attribute("href") or "", current_url)
        for a in el.query_selector_all("a[href]")
    ]
    interactive = [
        _capture_interactive_element(i, current_url)
        for i in el.query_selector_all(INTERACTIVE_SELECTOR)
    ]
    return dict(
        build_container_record(
            node,
            descendants=el.evaluate(_DESCENDANT_WALK_JS),
            links=links,
            interactive=interactive,
        )
    )


def _description_text(el) -> str | None:
    """Sanitized text of the expanded assignment's description block, if this
    element contains one. Read-only `.inner_text()`; no handler runs."""
    if el is None:
        return None
    block = el.query_selector(DESCRIPTION_BLOCK_SELECTOR)
    if block is None:
        return None
    text = sanitize_text_block(block.inner_text() or "")
    return text or None


def _assignment_row_candidates(page: Page, current_url: str) -> list[dict]:
    """For each control whose visible label matches a VERIFIED assignment
    action/status word, record its ancestor trail (tag/class/attrs per level)
    and one bounded structural capture of the outermost ancestor. Evidence for
    deciding at which nesting level a row's title/due/points/weight text lives.
    """
    candidates: list[dict] = []
    for control in page.query_selector_all(BUTTON_SELECTOR):
        label = _norm_label(
            control.inner_text() or control.get_attribute("value") or ""
        )
        if label not in ASSIGNMENT_ACTION_LABELS:
            continue
        chain = _ancestor_chain(control, ROW_ANCESTOR_LEVELS)
        outermost = chain[-1] if chain else None
        candidates.append(
            {
                "control": _capture_interactive_element(control, current_url),
                "ancestor_nodes": [_capture_node(a) for a in chain],
                "container": (
                    _capture_container(outermost, current_url) if outermost else None
                ),
                "description_text": _description_text(outermost),
            }
        )
        if len(candidates) >= MAX_ASSIGNMENT_ROWS:
            break
    return candidates


def _assignment_detail_candidate(page: Page, current_url: str) -> dict | None:
    """Structural capture around the first `h1` — meaningful only when the page
    is showing a single expanded assignment. Records the heading's ancestor
    trail and one bounded container capture so any id/`data-*`/href shared with
    a list-row candidate can be found by hand.
    """
    heading = page.query_selector("h1")
    if heading is None:
        return None
    chain = _ancestor_chain(heading, ROW_ANCESTOR_LEVELS)
    outermost = chain[-1] if chain else None
    return {
        "heading_text": sanitize_label(heading.inner_text() or ""),
        "ancestor_nodes": [_capture_node(a) for a in chain],
        "container": _capture_container(outermost, current_url) if outermost else None,
        "description_text": _description_text(outermost),
    }


def _capture_interactive_element(el, current_url: str) -> InteractiveElementRecord:
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

    return build_interactive_element_record(
        tag,
        label,
        current_url,
        attributes=attributes,
        data_attributes=data_attributes,
        onclick=raw_attrs.get("onclick"),
    )


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
            component = (
                "assignments component present"
                if snapshot["assignments_component_present"]
                else "no assignments component"
            )
            print(
                f"Captured: {snapshot['url']} "
                f"({len(snapshot['links'])} links, {len(snapshot['buttons'])} buttons, "
                f"{len(snapshot['interactive_elements'])} interactive elements, "
                f"{len(snapshot['assignment_row_candidates'])} assignment-row "
                f"candidates, {component})"
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
