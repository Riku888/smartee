"""Bounded, sanitized structural capture of one candidate DOM container.

Reconnaissance evidence only. Nothing here is a production selector contract
(CLAUDE.md Hard Rule 1) — it exists so a human can inspect, from LOCAL-only
recon output, how an assignments-list row associates its title / due-date /
points / grade-weight / status text with its interactive controls, and whether
an expanded assignment detail carries an identifier shared with a list row.

All values are sanitized (`sanitize_label` / credential redaction) and every
collection is capped, so a capture can never approach a full-DOM dump. Handlers
are never executed; form-field elements are skipped entirely.
"""

from collections.abc import Iterable, Mapping
from typing import TypedDict, cast

from smartee.resources.interactive import (
    InteractiveElementRecord,
    build_data_attributes,
    build_safe_attributes,
)
from smartee.resources.links import LinkRecord
from smartee.resources.sanitize import sanitize_label

# Keep one container's capture bounded (the operator may capture many rows).
MAX_DESCENDANTS = 60
MAX_CLASS_NAMES = 24
MAX_LINKS = 40
MAX_INTERACTIVE = 40
MAX_PATH_LENGTH = 160
_CLASS_TOKEN_MAX = 80

# Tags whose presence is structural evidence even with no direct text
# (e.g. an empty `<time>` wrapping a child, an empty `<td>` cell).
_SEMANTIC_TAGS = frozenset(
    {
        "time",
        "td",
        "th",
        "dt",
        "dd",
        "label",
        "caption",
        "summary",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "button",
    }
)

# Never record structural attributes/values for form fields.
_FORM_FIELD_TAGS = frozenset({"input", "textarea", "select", "option"})


class NodeRecord(TypedDict):
    tag: str
    class_names: list[str]
    attributes: dict[str, str]
    data_attribute_names: list[str]
    data_attributes: dict[str, str]


class DescendantRecord(NodeRecord):
    path: str
    text: str


class ContainerStructureRecord(NodeRecord):
    descendants: list[DescendantRecord]
    links: list[LinkRecord]
    interactive: list[InteractiveElementRecord]


def _class_names(class_value: str | None) -> list[str]:
    tokens: list[str] = []
    for raw in (class_value or "").split():
        token = sanitize_label(raw, max_length=_CLASS_TOKEN_MAX)
        if token:
            tokens.append(token)
        if len(tokens) >= MAX_CLASS_NAMES:
            break
    return tokens


def _clean_path(path: str) -> str:
    collapsed = " ".join(path.split())
    if len(collapsed) > MAX_PATH_LENGTH:
        collapsed = collapsed[:MAX_PATH_LENGTH].rstrip() + "…"
    return collapsed


def build_node_record(
    tag: str,
    class_value: str | None,
    *,
    attributes: Mapping[str, str | None],
    data_attributes: Mapping[str, str | None],
) -> NodeRecord:
    """Pure transform: one element's tag, class list, and safe structural
    attributes (`data-*` names always kept; values sanitized/redacted)."""
    data_names, data_values = build_data_attributes(data_attributes)
    return NodeRecord(
        tag=tag.strip().lower(),
        class_names=_class_names(class_value),
        attributes=build_safe_attributes(attributes),
        data_attribute_names=data_names,
        data_attributes=data_values,
    )


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _descendant_record(raw: Mapping[str, object]) -> DescendantRecord | None:
    tag = (_str_or_none(raw.get("tag")) or "").strip().lower()
    if not tag or tag in _FORM_FIELD_TAGS:
        return None

    attrs_obj = raw.get("attrs")
    attrs = (
        cast("dict[str, str | None]", attrs_obj) if isinstance(attrs_obj, dict) else {}
    )
    node = build_node_record(
        tag,
        _str_or_none(raw.get("class")),
        attributes=attrs,
        data_attributes=attrs,
    )
    text = sanitize_label(_str_or_none(raw.get("text")) or "")
    if not text and not node["data_attribute_names"] and tag not in _SEMANTIC_TAGS:
        return None

    return DescendantRecord(
        tag=node["tag"],
        class_names=node["class_names"],
        attributes=node["attributes"],
        data_attribute_names=node["data_attribute_names"],
        data_attributes=node["data_attributes"],
        path=_clean_path(_str_or_none(raw.get("path")) or ""),
        text=text,
    )


def build_container_record(
    node: NodeRecord,
    *,
    descendants: Iterable[Mapping[str, object]],
    links: Iterable[LinkRecord],
    interactive: Iterable[InteractiveElementRecord],
) -> ContainerStructureRecord:
    """Assemble one candidate container's bounded structural record from a
    prebuilt `NodeRecord` plus raw descendant dicts and already-sanitized link /
    interactive records. Pure and deterministic — no DOM access, no execution."""
    descendant_records: list[DescendantRecord] = []
    for raw in descendants:
        if len(descendant_records) >= MAX_DESCENDANTS:
            break
        record = _descendant_record(raw)
        if record is not None:
            descendant_records.append(record)

    return ContainerStructureRecord(
        tag=node["tag"],
        class_names=node["class_names"],
        attributes=node["attributes"],
        data_attribute_names=node["data_attribute_names"],
        data_attributes=node["data_attributes"],
        descendants=descendant_records,
        links=list(links)[:MAX_LINKS],
        interactive=list(interactive)[:MAX_INTERACTIVE],
    )
