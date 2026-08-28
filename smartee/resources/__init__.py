from smartee.resources.classify import classify_source_type
from smartee.resources.interactive import (
    INTERACTIVE_SELECTOR,
    REDACTED,
    SAFE_ATTRIBUTE_NAMES,
    InteractiveElementRecord,
    build_data_attributes,
    build_interactive_element_record,
    build_safe_attributes,
    sanitize_attribute_value,
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
    sanitize_text_block,
    sanitize_url,
)
from smartee.resources.structure import (
    ContainerStructureRecord,
    DescendantRecord,
    NodeRecord,
    build_container_record,
    build_node_record,
)

__all__ = [
    "INTERACTIVE_SELECTOR",
    "REDACTED",
    "SAFE_ATTRIBUTE_NAMES",
    "ContainerStructureRecord",
    "DescendantRecord",
    "DiscoveredResource",
    "InteractiveElementRecord",
    "LinkRecord",
    "NodeRecord",
    "ResolvedResource",
    "ResourceProvenance",
    "build_container_record",
    "build_data_attributes",
    "build_interactive_element_record",
    "build_link_record",
    "build_node_record",
    "build_safe_attributes",
    "classify_source_type",
    "domain_of",
    "is_same_origin",
    "looks_sensitive",
    "resolve_resource",
    "resolve_resources",
    "sanitize_attribute_value",
    "sanitize_label",
    "sanitize_text_block",
    "sanitize_url",
]
