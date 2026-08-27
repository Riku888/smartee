from typing import cast

from playwright.sync_api import Page

from scripts.recon_learning_suite import capture_page
from smartee.domain.enums import SourceType
from smartee.recon import (
    build_link_record,
    classify_source_type,
    domain_of,
    sanitize_url,
)


class _FakePage:
    """Minimal Playwright-Page double: only the surface capture_page reads."""

    def __init__(self, url: str):
        self.url = url

    def query_selector_all(self, _selector: str) -> list:
        return []

    def title(self) -> str:
        return "Fake Title"


def _fake_page(url: str) -> Page:
    return cast(Page, _FakePage(url))


def test_capture_page_url_field_is_sanitized_for_sso_redirect():
    raw = (
        "https://cas.byu.edu/cas/login?service=https%3A%2F%2Fexample.byu.edu%2Fcb"
        "&RelayState=abc&srid=id123&entityId=https%3A%2F%2Fokta.example%2Fsp"
    )
    snapshot = capture_page(_fake_page(raw))
    assert snapshot["url"] == "https://cas.byu.edu/cas/login"
    # Whatever gets printed to the console reads this same field, so a
    # console message built from `snapshot["url"]` can never diverge from
    # what's written to JSON — there is only one sanitized value.
    assert "RelayState" not in snapshot["url"]
    assert "srid" not in snapshot["url"]


def test_capture_page_never_falls_back_to_raw_url():
    snapshot = capture_page(_fake_page("not a url at all"))
    assert snapshot["url"] == "UNKNOWN"


def test_sanitize_url_strips_fragment():
    assert sanitize_url("https://learningsuite.byu.edu/course/1#top") == (
        "https://learningsuite.byu.edu/course/1"
    )


def test_sanitize_url_strips_sensitive_query_params():
    raw = "https://example.com/page?token=abc123&course=cyber465&session=xyz"
    sanitized = sanitize_url(raw)
    assert sanitized is not None
    assert "token" not in sanitized
    assert "session" not in sanitized
    assert "course=cyber465" in sanitized


def test_sanitize_url_keeps_non_sensitive_query_params():
    raw = "https://example.com/page?week=8&course=cyber465"
    sanitized = sanitize_url(raw)
    assert sanitized == raw


def test_sanitize_url_rejects_non_http_schemes():
    assert sanitize_url("javascript:void(0)") is None
    assert sanitize_url("mailto:someone@byu.edu") is None
    assert sanitize_url("data:text/plain;base64,aGVsbG8=") is None


def test_sanitize_url_rejects_unparseable_input():
    assert sanitize_url("not a url at all") is None


def test_domain_of_extracts_hostname():
    assert (
        domain_of("https://LearningSuite.byu.edu/course/1") == "learningsuite.byu.edu"
    )


def test_domain_of_returns_none_for_relative_or_invalid():
    assert domain_of("/course/1") is None
    assert domain_of("javascript:void(0)") is None


def test_classify_source_type_learning_suite():
    assert (
        classify_source_type("https://learningsuite.byu.edu/course/1")
        == SourceType.LEARNING_SUITE
    )


def test_classify_source_type_box():
    assert classify_source_type("https://byu.box.com/s/abc123") == SourceType.BOX


def test_classify_source_type_youtube():
    assert classify_source_type("https://youtu.be/abc123") == SourceType.YOUTUBE
    assert (
        classify_source_type("https://www.youtube.com/watch?v=abc123")
        == SourceType.YOUTUBE
    )


def test_classify_source_type_direct_document():
    assert (
        classify_source_type("https://example.com/files/lecture-08.pdf")
        == SourceType.DIRECT_DOCUMENT
    )


def test_classify_source_type_external_web():
    assert (
        classify_source_type("https://example.com/article") == SourceType.EXTERNAL_WEB
    )


def test_classify_source_type_unknown_for_non_http_scheme():
    assert classify_source_type("javascript:void(0)") == SourceType.UNKNOWN
    assert classify_source_type("mailto:someone@byu.edu") == SourceType.UNKNOWN


def test_build_link_record_same_origin():
    record = build_link_record(
        " Syllabus ",
        "https://learningsuite.byu.edu/course/1/syllabus",
        "https://learningsuite.byu.edu/course/1",
    )
    assert record["text"] == "Syllabus"
    assert record["same_origin"] is True
    assert record["source_type"] == SourceType.LEARNING_SUITE.value


def test_build_link_record_resolves_relative_href_as_learning_suite():
    record = build_link_record(
        "Week 3 Notes",
        "/course/student/pages/id-123",
        "https://learningsuite.byu.edu/course/student/home",
    )
    assert record["href"] == "https://learningsuite.byu.edu/course/student/pages/id-123"
    assert record["domain"] == "learningsuite.byu.edu"
    assert record["source_type"] == SourceType.LEARNING_SUITE.value
    assert record["same_origin"] is True


def test_build_link_record_resolves_relative_href_and_still_sanitizes_query():
    record = build_link_record(
        "Assignment",
        "/course/student/home/assignments?token=secret&week=8",
        "https://learningsuite.byu.edu/course/student/home",
    )
    assert record["href"] is not None
    assert "token" not in record["href"]
    assert "week=8" in record["href"]


def test_build_link_record_relative_href_does_not_resolve_across_origin():
    record = build_link_record(
        "External resource",
        "//box.com/s/abc123",
        "https://learningsuite.byu.edu/course/student/home",
    )
    assert record["domain"] == "box.com"
    assert record["source_type"] == SourceType.BOX.value
    assert record["same_origin"] is False


def test_build_link_record_external_and_sanitized():
    record = build_link_record(
        "Lecture Recording",
        "https://youtu.be/abc123?list=xyz&token=secret",
        "https://learningsuite.byu.edu/course/1",
    )
    assert record["same_origin"] is False
    assert record["source_type"] == SourceType.YOUTUBE.value
    assert record["href"] is not None
    assert "token" not in record["href"]


def test_sanitize_url_strips_entire_query_for_cas_sso():
    # Real shape observed in recon captures: a CAS/SAML redirect carries
    # auth-flow state (RelayState, srid, entityId, service) that isn't
    # caught by the generic sensitive-substring list.
    raw = (
        "https://cas.byu.edu/cas/login?service=https%3A%2F%2Fexample.byu.edu%2Fcb"
        "&RelayState=abc&srid=id123&entityId=https%3A%2F%2Fokta.example%2Fsp"
    )
    sanitized = sanitize_url(raw)
    assert sanitized == "https://cas.byu.edu/cas/login"


def test_sanitize_url_strips_entire_query_for_okta_host():
    raw = "https://example.okta.com/oauth2/v1/authorize?okta_key=abc123&week=8"
    sanitized = sanitize_url(raw)
    assert sanitized == "https://example.okta.com/oauth2/v1/authorize"


def test_build_link_record_drops_unsupported_scheme_href():
    record = build_link_record(
        "Email instructor",
        "mailto:prof@byu.edu",
        "https://learningsuite.byu.edu/course/1",
    )
    assert record["href"] is None
    assert record["source_type"] == SourceType.UNKNOWN.value
