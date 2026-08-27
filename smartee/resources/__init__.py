from smartee.resources.classify import classify_source_type
from smartee.resources.interactive import (
    INTERACTIVE_SELECTOR,
    REDACTED,
    SAFE_ATTRIBUTE_NAMES,
    InteractiveElementRecord,
    build_interactive_element_record,
)
from smartee.resources.links import LinkRecord, build_link_record
from smartee.resources.resolver import (
    DiscoveredResource,
    ResolvedResource,
    ResourceProvenance,
    resolve_resource,
    resolve_resources,
)
from smartee.resources.sanitize import (
    domain_of,
    is_same_origin,
    looks_sensitive,
    sanitize_label,
    sanitize_url,
)

__all__ = [
    "INTERACTIVE_SELECTOR",
    "REDACTED",
    "SAFE_ATTRIBUTE_NAMES",
    "DiscoveredResource",
    "InteractiveElementRecord",
    "LinkRecord",
    "ResolvedResource",
    "ResourceProvenance",
    "build_interactive_element_record",
    "build_link_record",
    "classify_source_type",
    "domain_of",
    "is_same_origin",
    "looks_sensitive",
    "resolve_resource",
    "resolve_resources",
    "sanitize_label",
    "sanitize_url",
]
