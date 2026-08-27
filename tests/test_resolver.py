from datetime import UTC, datetime

from smartee.domain.enums import SourceType
from smartee.resources import (
    DiscoveredResource,
    resolve_resource,
    resolve_resources,
    sanitize_label,
)

# Synthetic fixtures only. No real course names, course ids, or private URLs.
_LS_PAGE = "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/pages/id-example"


def _discovered(raw_href: str, *, page: str = _LS_PAGE, text: str = "link"):
    return DiscoveredResource(raw_href=raw_href, source_page_url=page, link_text=text)


def test_resolves_relative_href_against_source_page_as_learning_suite():
    resolved = resolve_resource(_discovered("../pages/id-other"))
    assert resolved.source_type is SourceType.LEARNING_SUITE
    assert resolved.url == (
        "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/pages/id-other"
    )
    assert resolved.domain == "learningsuite.byu.edu"
    assert resolved.same_origin is True


def test_protocol_relative_href_resolves_to_box():
    resolved = resolve_resource(_discovered("//byu.app.box.com/s/example"))
    assert resolved.source_type is SourceType.BOX
    assert resolved.same_origin is False


def test_box_bare_and_app_hostnames_both_classify_as_box():
    for host in ("byu.box.com", "byu.app.box.com"):
        resolved = resolve_resource(_discovered(f"https://{host}/s/example"))
        assert resolved.source_type is SourceType.BOX


def test_youtube_short_and_watch_forms_classify_as_youtube():
    for href in (
        "https://youtu.be/exampleid",
        "https://www.youtube.com/watch?v=exampleid",
    ):
        assert resolve_resource(_discovered(href)).source_type is SourceType.YOUTUBE


def test_direct_document_on_byu_subdomain():
    resolved = resolve_resource(
        _discovered("https://capstone.example.byu.edu/files/report.pdf")
    )
    assert resolved.source_type is SourceType.DIRECT_DOCUMENT


def test_byu_external_platform_stays_external_web():
    # OBSERVATIONS.md: BYU-external platforms (Zoom, capstone/support sites) are
    # linked from course content, but what happens when followed is UNKNOWN
    # (open question #3). They must not get a distinct type yet.
    for href in (
        "https://byu.zoom.us/j/0000000000",
        "https://support.example.byu.edu/help/article",
        "https://learnanywhere.example.byu.edu/module/1",
    ):
        assert (
            resolve_resource(_discovered(href)).source_type is SourceType.EXTERNAL_WEB
        )


def test_arbitrary_public_site_is_external_web():
    resolved = resolve_resource(_discovered("https://news.example.com/story"))
    assert resolved.source_type is SourceType.EXTERNAL_WEB


def test_unsupported_scheme_is_unknown_with_no_url():
    resolved = resolve_resource(_discovered("mailto:prof@example.byu.edu"))
    assert resolved.source_type is SourceType.UNKNOWN
    assert resolved.url is None


def test_relative_href_with_unusable_source_page_degrades_to_unknown():
    resolved = resolve_resource(
        DiscoveredResource(raw_href="pages/id-x", source_page_url="UNKNOWN")
    )
    assert resolved.source_type is SourceType.UNKNOWN
    assert resolved.url is None


def test_query_is_sanitized_in_resolved_url():
    resolved = resolve_resource(
        _discovered("https://www.youtube.com/watch?v=exampleid&token=sekret&list=wk8")
    )
    assert resolved.url is not None
    assert "token" not in resolved.url
    assert "v=exampleid" in resolved.url


def test_provenance_is_preserved_and_sanitized():
    when = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    resource = DiscoveredResource(
        raw_href="/.-ZL-/cid-0000/student/pages/id-other",
        source_page_url="https://cas.byu.edu/cas/login?service=x&RelayState=abc",
        link_text="notes",
        discovered_at=when,
    )
    resolved = resolve_resource(resource)
    assert resolved.provenance.source_page_url == "https://cas.byu.edu/cas/login"
    assert resolved.provenance.source_page_domain == "cas.byu.edu"
    assert resolved.provenance.discovered_at == when


def test_label_is_sanitized():
    resolved = resolve_resource(
        _discovered("https://example.com/x", text="  Week\t3\n\nNotes  ")
    )
    assert resolved.label == "Week 3 Notes"


def test_sanitize_label_strips_control_chars_and_truncates():
    assert sanitize_label("a\x00b\x1fc") == "a b c"
    assert sanitize_label("x" * 250).endswith("…")
    assert len(sanitize_label("x" * 250)) == 201


def test_resolve_resources_preserves_order():
    resolved = resolve_resources(
        [
            _discovered("https://youtu.be/one"),
            _discovered("https://byu.box.com/s/two"),
        ]
    )
    assert [r.source_type for r in resolved] == [SourceType.YOUTUBE, SourceType.BOX]
