"""Deterministic sanitization tests for generic interactive-element capture.

Synthetic inputs only — no real course ids, private URLs, or captured values.
"""

from smartee.resources import (
    REDACTED,
    build_interactive_element_record,
    looks_sensitive,
)

_PAGE = "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/home"


def _record(*, attributes=None, data_attributes=None, onclick=None, label="Course"):
    return build_interactive_element_record(
        "DIV",
        label,
        _PAGE,
        attributes=attributes or {},
        data_attributes=data_attributes or {},
        onclick=onclick,
    )


def test_tag_and_label_are_normalized_and_inert():
    record = _record(label="  Intro\x00 to\r\n Things   ")
    assert record["tag"] == "div"
    assert record["label"] == "Intro to Things"


def test_label_is_length_capped():
    record = _record(label="x" * 500)
    assert len(record["label"]) <= 201  # 200 chars + ellipsis
    assert record["label"].endswith("…")


def test_href_is_routed_through_shared_link_logic():
    record = _record(
        attributes={"href": "/.-ZL-/cid-0000/student/pages/id-x?token=s&week=8"}
    )
    assert record["link"] is not None
    assert record["link"]["domain"] == "learningsuite.byu.edu"
    assert record["link"]["source_type"] == "learning_suite"
    assert record["link"]["href"] is not None
    assert "token" not in record["link"]["href"]
    assert "week=8" in record["link"]["href"]


def test_missing_or_empty_href_yields_no_link():
    assert _record()["link"] is None
    assert _record(attributes={"href": ""})["link"] is None


def test_non_http_href_is_captured_as_link_with_no_url():
    record = _record(attributes={"href": "javascript:void(0)"})
    assert record["link"] is not None
    assert record["link"]["href"] is None
    assert record["link"]["source_type"] == "unknown"


def test_safe_structural_attributes_are_kept_inert():
    record = _record(
        attributes={
            "id": "course-entry-3",
            "role": "button",
            "aria-expanded": "false",
            "aria-controls": "panel-3",
            "type": "button",
        }
    )
    assert record["attributes"] == {
        "id": "course-entry-3",
        "role": "button",
        "aria-expanded": "false",
        "aria-controls": "panel-3",
        "type": "button",
    }


def test_href_is_not_duplicated_into_attributes_map():
    record = _record(attributes={"href": "/x", "id": "y"})
    assert "href" not in record["attributes"]
    assert record["attributes"] == {"id": "y"}


def test_safe_attribute_with_sensitive_value_is_redacted_but_kept_as_key():
    record = _record(attributes={"aria-label": "session-token for user"})
    assert record["attributes"]["aria-label"] == REDACTED


def test_data_attribute_names_are_always_recorded_sorted():
    record = _record(
        data_attributes={
            "data-course-id": "abc",
            "data-auth-key": "zzz",
            "data-tab": "1",
        }
    )
    assert record["data_attribute_names"] == [
        "data-auth-key",
        "data-course-id",
        "data-tab",
    ]


def test_data_attribute_value_redacted_when_name_looks_sensitive():
    record = _record(data_attributes={"data-session-id": "s-12345"})
    assert "data-session-id" in record["data_attribute_names"]
    assert record["data_attributes"]["data-session-id"] == REDACTED


def test_data_attribute_value_redacted_when_value_looks_sensitive():
    record = _record(data_attributes={"data-target": "Bearer jwt.header.payload"})
    assert record["data_attributes"]["data-target"] == REDACTED


def test_benign_data_attribute_value_is_kept_inert():
    record = _record(data_attributes={"data-course-index": "  3 \x00"})
    assert record["data_attributes"]["data-course-index"] == "3"


def test_onclick_absent_is_none():
    assert _record()["onclick"] is None


def test_onclick_benign_is_reduced_to_inert_representation():
    record = _record(onclick="showCoursePanel(3);\n  return false;")
    assert record["onclick"] == "showCoursePanel(3); return false;"


def test_onclick_sensitive_is_redacted():
    record = _record(onclick="fetch('/api?session_token=abc')")
    assert record["onclick"] == REDACTED


def test_looks_sensitive_matches_credential_session_auth_terms():
    for text in (
        "session",
        "auth-state",
        "csrfToken",
        "data-jwt",
        "OAuth2",
        "duo-device",
        "X-Bearer",
    ):
        assert looks_sensitive(text) is True


def test_looks_sensitive_false_for_ordinary_structural_text():
    for text in ("course-id", "aria-expanded", "tab-index", "panel-3", "button"):
        assert looks_sensitive(text) is False


def test_looks_sensitive_false_for_words_that_merely_contain_a_term():
    # "assignment" contains the sensitive term "sig" as a bare substring; none
    # of these are credential-related and none must be redacted.
    for text in (
        "assignment",
        "data-assignment-id",
        "assignments",
        "reassignment",
        "assignee",
        "design",
        "designation",
    ):
        assert looks_sensitive(text) is False


def test_looks_sensitive_true_for_boundary_credential_terms():
    for text in (
        "sig",
        "signature",
        "x-signature",
        "authToken",
        "sessionId",
        "session_token",
        "csrfToken",
        "api-token",
        "oauth2",
        "data-jwt",
    ):
        assert looks_sensitive(text) is True
