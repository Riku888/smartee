from collections.abc import Mapping
from typing import TypedDict

from smartee.resources.links import LinkRecord, build_link_record
from smartee.resources.sanitize import looks_sensitive, sanitize_label

# Generic interactive-element selector. Deliberately not specific to Learning
# Suite course entries — it is the same broad set for any page.
INTERACTIVE_SELECTOR = 'a, button, [role="button"]'

# Structural attributes that are safe to record verbatim (after inert-label
# sanitization). `href` is handled separately via the shared link logic.
SAFE_ATTRIBUTE_NAMES: tuple[str, ...] = (
    "id",
    "role",
    "aria-label",
    "aria-controls",
    "aria-expanded",
    "type",
)

REDACTED = "[redacted]"


class InteractiveElementRecord(TypedDict):
    tag: str
    label: str
    link: LinkRecord | None
    attributes: dict[str, str]
    data_attribute_names: list[str]
    data_attributes: dict[str, str]
    onclick: str | None


def _redacted_value(name: str, value: str) -> str:
    if looks_sensitive(name) or looks_sensitive(value):
        return REDACTED
    return sanitize_label(value)


def build_interactive_element_record(
    tag: str,
    label: str,
    current_url: str,
    *,
    attributes: Mapping[str, str | None],
    data_attributes: Mapping[str, str | None],
    onclick: str | None = None,
) -> InteractiveElementRecord:
    """Pure, deterministic transform from a raw interactive element's observed
    attributes to a sanitized record. Never inspects or invents page structure;
    the caller supplies whatever the DOM returned. No LLM, no network, no
    execution of any handler.

    - `label` is reduced to an inert one-line string (`sanitize_label`).
    - `href` (if any) is routed through the shared `build_link_record` so its
      sanitization never diverges from ordinary link handling.
    - Other structural attributes are kept inert-and-capped, or replaced with
      `REDACTED` when the attribute name or value looks credential/session/auth
      related.
    - `data-*` attribute NAMES are always recorded. `data-*` VALUES are kept
      (inert-and-capped) or `REDACTED`; callers must write them only to the
      local gitignored recon output, never to the terminal or committed files.
    - `onclick`, if present, is recorded only as a sanitized representation and
      is never executed.
    """
    href = attributes.get("href")
    link = (
        build_link_record(label, href, current_url)
        if href is not None and href != ""
        else None
    )

    safe_attributes = {
        name: _redacted_value(name, value)
        for name in SAFE_ATTRIBUTE_NAMES
        if (value := attributes.get(name)) is not None
    }

    data_names = sorted(data_attributes)
    data_values = {
        name: _redacted_value(name, value if value is not None else "")
        for name in data_names
        if (value := data_attributes.get(name)) is not None
    }

    return InteractiveElementRecord(
        tag=tag.strip().lower(),
        label=sanitize_label(label),
        link=link,
        attributes=safe_attributes,
        data_attribute_names=data_names,
        data_attributes=data_values,
        onclick=_sanitize_onclick(onclick),
    )


def _sanitize_onclick(onclick: str | None) -> str | None:
    """Inert, local-only representation of an inline handler. Never executed."""
    if onclick is None:
        return None
    if looks_sensitive(onclick):
        return REDACTED
    return sanitize_label(onclick)
