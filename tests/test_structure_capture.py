"""Deterministic sanitization/bounding tests for candidate-container capture.

Synthetic inputs only — no real course ids, private URLs, or captured DOM.
"""

from smartee.resources import (
    REDACTED,
    build_container_record,
    build_interactive_element_record,
    build_link_record,
    build_node_record,
)
from smartee.resources.structure import (
    MAX_DESCENDANTS,
    MAX_INTERACTIVE,
    MAX_LINKS,
    MAX_PATH_LENGTH,
)

_PAGE = "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/home/assignments"


def _node(tag="div", class_value=None, attrs=None, data=None):
    return build_node_record(
        tag,
        class_value,
        attributes=attrs or {},
        data_attributes=data or {},
    )


# --- build_node_record ------------------------------------------------------


def test_node_tag_normalized_and_class_split():
    node = _node(tag="  DIV ", class_value="assignment-row  is-open\tflex")
    assert node["tag"] == "div"
    assert node["class_names"] == ["assignment-row", "is-open", "flex"]


def test_node_class_list_is_capped():
    node = _node(class_value=" ".join(f"c{i}" for i in range(200)))
    assert len(node["class_names"]) == 24


def test_node_keeps_only_safe_attributes():
    node = _node(
        attrs={
            "id": "row-3",
            "role": "row",
            "aria-label": "Lab 1 due Friday",
            "style": "color:red",
            "value": "should-never-be-captured",
        }
    )
    assert node["attributes"] == {
        "id": "row-3",
        "role": "row",
        "aria-label": "Lab 1 due Friday",
    }


def test_assignment_identifiers_are_not_redacted():
    # "assignment" contains "sig" but is not credential-related: the id value
    # and the data-assignment-id name+value must survive for row association.
    node = _node(
        attrs={"id": "assignment-3"},
        data={"data-assignment-id": "a-42"},
    )
    assert node["attributes"]["id"] == "assignment-3"
    assert node["data_attribute_names"] == ["data-assignment-id"]
    assert node["data_attributes"]["data-assignment-id"] == "a-42"


def test_signature_and_auth_identifiers_are_still_redacted():
    node = _node(
        attrs={"id": "request-signature"},
        data={"data-session-token": "s-1", "data-auth": "x"},
    )
    assert node["attributes"]["id"] == REDACTED
    assert node["data_attributes"]["data-session-token"] == REDACTED
    assert node["data_attributes"]["data-auth"] == REDACTED


def test_time_datetime_attribute_is_kept():
    # The `<time datetime>` value is the deterministic due-date signal on an
    # assignments-list row; it must survive structural capture.
    node = _node(tag="time", attrs={"datetime": "2026-09-15T23:59:00-06:00"})
    assert node["attributes"]["datetime"] == "2026-09-15T23:59:00-06:00"


def test_descendant_time_element_keeps_datetime():
    container = _container(
        [
            {
                "tag": "time",
                "path": "/div[3]/span[1]/time[1]",
                "text": "Sep 15",
                "attrs": {"datetime": "2026-09-15", "style": "x"},
            }
        ]
    )
    (desc,) = container["descendants"]
    assert desc["tag"] == "time"
    assert desc["attributes"] == {"datetime": "2026-09-15"}
    assert desc["text"] == "Sep 15"


def test_node_redacts_sensitive_attribute_value_but_keeps_key():
    node = _node(attrs={"aria-label": "session-token abc123"})
    assert node["attributes"]["aria-label"] == REDACTED


def test_node_data_names_sorted_and_values_sanitized():
    node = _node(
        data={
            "data-item-ref": "  a-42 \x00",
            "data-auth-token": "zzz",
            "data-col": "due",
        }
    )
    assert node["data_attribute_names"] == [
        "data-auth-token",
        "data-col",
        "data-item-ref",
    ]
    assert node["data_attributes"]["data-item-ref"] == "a-42"
    assert node["data_attributes"]["data-auth-token"] == REDACTED


def test_node_ignores_non_data_prefixed_keys_in_data_map():
    node = _node(data={"onclick": "doThing()", "data-x": "1"})
    assert node["data_attribute_names"] == ["data-x"]


# --- build_container_record: descendants ------------------------------------


def _container(descendants, *, links=None, interactive=None):
    return build_container_record(
        _node(tag="li", class_value="assignment"),
        descendants=descendants,
        links=links or [],
        interactive=interactive or [],
    )


def test_container_carries_node_fields():
    container = _container([])
    assert container["tag"] == "li"
    assert container["class_names"] == ["assignment"]
    assert container["descendants"] == []


def test_descendant_text_is_sanitized_and_path_kept():
    container = _container(
        [{"tag": "SPAN", "path": "/div[1]/span[2]", "text": " Due\x00 Fri  11:59pm "}]
    )
    (desc,) = container["descendants"]
    assert desc["tag"] == "span"
    assert desc["path"] == "/div[1]/span[2]"
    assert desc["text"] == "Due Fri 11:59pm"


def test_descendant_path_is_length_capped():
    container = _container([{"tag": "span", "path": "/a[1]" * 100, "text": "x"}])
    assert len(container["descendants"][0]["path"]) <= MAX_PATH_LENGTH + 1


def test_empty_wrapper_descendant_is_dropped():
    container = _container([{"tag": "div", "path": "/div[1]", "text": "   "}])
    assert container["descendants"] == []


def test_empty_semantic_descendant_is_kept():
    container = _container([{"tag": "time", "path": "/time[1]", "text": ""}])
    assert [d["tag"] for d in container["descendants"]] == ["time"]


def test_empty_descendant_with_data_attr_is_kept_for_association():
    container = _container(
        [
            {
                "tag": "div",
                "path": "/div[1]",
                "text": "",
                "attrs": {"data-item-ref": "a-42"},
            }
        ]
    )
    (desc,) = container["descendants"]
    assert desc["data_attributes"]["data-item-ref"] == "a-42"


def test_form_field_descendants_are_never_recorded():
    container = _container(
        [
            {
                "tag": "input",
                "path": "/input[1]",
                "text": "",
                "attrs": {"value": "sec"},
            },
            {"tag": "select", "path": "/select[1]", "text": "opt"},
        ]
    )
    assert container["descendants"] == []


def test_descendants_are_capped():
    raw = [
        {"tag": "span", "path": f"/span[{i}]", "text": f"t{i}"}
        for i in range(MAX_DESCENDANTS + 25)
    ]
    assert len(_container(raw)["descendants"]) == MAX_DESCENDANTS


def test_descendant_attrs_only_expose_safe_and_data_keys():
    container = _container(
        [
            {
                "tag": "a",
                "path": "/a[1]",
                "text": "open",
                "attrs": {
                    "id": "x",
                    "href": "/secret?token=abc",
                    "style": "x",
                    "data-k": "v",
                },
            }
        ]
    )
    (desc,) = container["descendants"]
    assert desc["attributes"] == {"id": "x"}
    assert desc["data_attributes"] == {"data-k": "v"}


# --- build_container_record: links / interactive ---------------------------


def test_links_are_capped():
    links = [
        build_link_record("l", f"/pages/id-{i}", _PAGE) for i in range(MAX_LINKS + 10)
    ]
    assert len(_container([], links=links)["links"]) == MAX_LINKS


def test_interactive_records_are_capped():
    interactive = [
        build_interactive_element_record(
            "button", f"b{i}", _PAGE, attributes={}, data_attributes={}
        )
        for i in range(MAX_INTERACTIVE + 10)
    ]
    got = _container([], interactive=interactive)["interactive"]
    assert len(got) == MAX_INTERACTIVE
