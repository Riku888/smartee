from datetime import UTC, datetime

from smartee.course import CourseEntryObservation, resolve_course_entry
from smartee.domain.enums import CourseEntryType

# Synthetic fixtures only. No real course ids or private course URLs.
_LS_ENTRY = "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/home/enter"
_LS_PAGE = "https://learningsuite.byu.edu/.-ZL-/cid-0000/student/pages/id-example"


def _observed(final_url: str, *, entry: str = _LS_ENTRY):
    return CourseEntryObservation(entry_url=entry, final_url=final_url)


def test_learning_suite_to_learning_suite_is_native_no_cross_origin():
    resolved = resolve_course_entry(_observed(_LS_PAGE))
    assert resolved.entry_type is CourseEntryType.LEARNING_SUITE_NATIVE
    assert resolved.resolved_url == _LS_PAGE
    assert resolved.final_domain == "learningsuite.byu.edu"
    assert resolved.cross_origin is False
    assert resolved.provenance.entry_domain == "learningsuite.byu.edu"


def test_learning_suite_to_external_domain_is_external_platform_cross_origin():
    resolved = resolve_course_entry(
        _observed("https://courseware.example.edu/section/1")
    )
    assert resolved.entry_type is CourseEntryType.EXTERNAL_PLATFORM
    assert resolved.final_domain == "courseware.example.edu"
    assert resolved.cross_origin is True
    # provenance still points back at the Learning Suite entry
    assert resolved.provenance.entry_url == _LS_ENTRY


def test_relative_final_url_resolves_against_entry_and_stays_native():
    resolved = resolve_course_entry(_observed("../pages/id-example"))
    assert resolved.resolved_url == _LS_PAGE
    assert resolved.entry_type is CourseEntryType.LEARNING_SUITE_NATIVE
    assert resolved.cross_origin is False


def test_protocol_relative_final_url_is_external_platform():
    resolved = resolve_course_entry(_observed("//courseware.example.edu/x"))
    assert resolved.entry_type is CourseEntryType.EXTERNAL_PLATFORM
    assert resolved.final_domain == "courseware.example.edu"
    assert resolved.cross_origin is True


def test_output_is_sanitized_fragments_and_sensitive_query_dropped():
    resolved = resolve_course_entry(
        CourseEntryObservation(
            entry_url="https://cas.byu.edu/cas/login?service=x&RelayState=abc",
            final_url="https://courseware.example.edu/x?session_token=sekret&unit=3#top",
        )
    )
    assert resolved.resolved_url is not None
    assert "sekret" not in resolved.resolved_url
    assert "session_token" not in resolved.resolved_url
    assert "#top" not in resolved.resolved_url
    assert "unit=3" in resolved.resolved_url
    # entire query on SSO hosts is dropped
    assert resolved.provenance.entry_url == "https://cas.byu.edu/cas/login"


def test_unusable_final_url_is_unknown_with_no_resolved_url():
    resolved = resolve_course_entry(_observed("javascript:void(0)"))
    assert resolved.entry_type is CourseEntryType.UNKNOWN
    assert resolved.resolved_url is None
    assert resolved.final_domain is None


def test_relative_final_with_unusable_entry_degrades_to_unknown():
    resolved = resolve_course_entry(
        CourseEntryObservation(entry_url="UNKNOWN", final_url="pages/id-x")
    )
    assert resolved.entry_type is CourseEntryType.UNKNOWN
    assert resolved.resolved_url is None
    assert resolved.cross_origin is None


def test_external_final_with_unusable_entry_has_unknown_cross_origin():
    resolved = resolve_course_entry(
        CourseEntryObservation(
            entry_url="UNKNOWN",
            final_url="https://courseware.example.edu/x",
        )
    )
    assert resolved.entry_type is CourseEntryType.EXTERNAL_PLATFORM
    assert resolved.cross_origin is None
    assert resolved.provenance.entry_url is None


def test_observed_at_is_preserved_in_provenance():
    when = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    resolved = resolve_course_entry(
        CourseEntryObservation(
            entry_url=_LS_ENTRY, final_url=_LS_PAGE, observed_at=when
        )
    )
    assert resolved.provenance.observed_at == when
