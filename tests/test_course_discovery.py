"""Deterministic tests for core Course Discovery.

Synthetic inputs only — no real course ids or private course URLs. Course
structure mirrors the clean in-course Course Switcher capture: a toggle
<button aria-label="Show course selection menu ..."> plus one <a> per course
whose href path contains `/student/cid-<id>/`.
"""

from datetime import UTC, datetime

from smartee.course import CourseMenuObservation, discover_courses
from smartee.resources import build_interactive_element_record

_PAGE = "https://learningsuite.byu.edu/.MjTJ/student/top"


def _element(tag, label, *, href=None, attributes=None):
    attrs = dict(attributes or {})
    if href is not None:
        attrs["href"] = href
    return build_interactive_element_record(
        tag, label, _PAGE, attributes=attrs, data_attributes={}
    )


def _toggle(expanded=True):
    return _element(
        "BUTTON",
        "FALL 2026 DEPT 100 - A Course",
        attributes={
            "aria-label": "Show course selection menu. Current course: DEPT 100",
            "aria-expanded": "true" if expanded else "false",
        },
    )


def _course_link(label, cid, *, absolute=True):
    path = f"/.MjTJ/student/cid-{cid}/student/home/dashboard"
    href = f"https://learningsuite.byu.edu{path}" if absolute else path
    return _element("A", label, href=href)


def _observe(*elements, observed_term=None, observed_at=None):
    return CourseMenuObservation(
        elements=list(elements),
        menu_page_url=_PAGE,
        observed_term=observed_term,
        observed_at=observed_at,
    )


def test_one_valid_course():
    result = discover_courses(
        _observe(_toggle(), _course_link("DEPT 100 - A Course", "aaa111"))
    )
    assert result.menu_expanded is True
    assert len(result.courses) == 1
    course = result.courses[0]
    assert course.course_id == "aaa111"
    assert course.label == "DEPT 100 - A Course"
    assert course.entry_url == (
        "https://learningsuite.byu.edu/.MjTJ/student/cid-aaa111/student/home/dashboard"
    )
    assert course.term is None
    assert course.provenance.menu_page_url == _PAGE
    assert course.provenance.menu_page_domain == "learningsuite.byu.edu"


def test_multiple_courses_preserve_order():
    result = discover_courses(
        _observe(
            _toggle(),
            _course_link("DEPT 100", "aaa"),
            _course_link("DEPT 200", "bbb"),
            _course_link("DEPT 300", "ccc"),
        )
    )
    assert [c.course_id for c in result.courses] == ["aaa", "bbb", "ccc"]


def test_duplicate_course_id_is_deduplicated_first_wins():
    result = discover_courses(
        _observe(
            _toggle(),
            _course_link("DEPT 100 - Primary", "dup"),
            _course_link("DEPT 100 - Repeat Entry", "dup"),
        )
    )
    assert len(result.courses) == 1
    assert result.courses[0].label == "DEPT 100 - Primary"


def test_malformed_cid_segment_is_skipped():
    empty_token = _element(
        "A", "No token", href="https://learningsuite.byu.edu/.MjTJ/student/cid-/x"
    )
    no_dash = _element(
        "A", "No dash", href="https://learningsuite.byu.edu/.MjTJ/student/cidXYZ/x"
    )
    wrong_prefix = _element(
        "A", "Wrong prefix", href="https://learningsuite.byu.edu/cas/cid-abc/student/x"
    )
    result = discover_courses(_observe(_toggle(), empty_token, no_dash, wrong_prefix))
    assert result.menu_expanded is True
    assert result.courses == []


def test_all_courses_link_is_excluded():
    all_courses = _element(
        "A",
        "All Courses",
        href="https://learningsuite.byu.edu/.MjTJ/student/student/top",
    )
    result = discover_courses(
        _observe(_toggle(), all_courses, _course_link("DEPT 100", "real"))
    )
    assert [c.course_id for c in result.courses] == ["real"]


def test_relative_and_absolute_hrefs_yield_same_absolute_entry_url():
    result = discover_courses(
        _observe(
            _toggle(),
            _course_link("Absolute", "abs1", absolute=True),
            _course_link("Relative", "rel1", absolute=False),
        )
    )
    urls = {c.course_id: c.entry_url for c in result.courses}
    assert urls["abs1"] == (
        "https://learningsuite.byu.edu/.MjTJ/student/cid-abs1/student/home/dashboard"
    )
    assert urls["rel1"] == (
        "https://learningsuite.byu.edu/.MjTJ/student/cid-rel1/student/home/dashboard"
    )


def test_label_and_url_output_are_sanitized():
    noisy = _element(
        "A",
        "  DEPT\x00 100\r\n  Injected  ",
        href=(
            "https://learningsuite.byu.edu/.MjTJ/student/cid-san1/student/home"
            "/dashboard?session=leak&week=8#frag"
        ),
    )
    result = discover_courses(_observe(_toggle(), noisy))
    course = result.courses[0]
    assert course.label == "DEPT 100 Injected"
    assert "session" not in course.entry_url
    assert "#frag" not in course.entry_url
    assert "week=8" in course.entry_url


def test_term_is_none_when_not_directly_observed():
    result = discover_courses(
        _observe(_toggle(), _course_link("DEPT 100", "aaa"), observed_term=None)
    )
    assert result.courses[0].term is None

    blank = discover_courses(
        _observe(_toggle(), _course_link("DEPT 100", "aaa"), observed_term="   ")
    )
    assert blank.courses[0].term is None


def test_term_is_passed_through_sanitized_when_directly_observed():
    result = discover_courses(
        _observe(
            _toggle(),
            _course_link("DEPT 100", "aaa"),
            observed_term="  Fall\x00 2026 ",
        )
    )
    assert result.courses[0].term == "Fall 2026"


def test_menu_not_expanded_yields_no_courses():
    collapsed = discover_courses(
        _observe(_toggle(expanded=False), _course_link("DEPT 100", "aaa"))
    )
    assert collapsed.menu_expanded is False
    assert collapsed.courses == []

    no_toggle = discover_courses(_observe(_course_link("DEPT 100", "aaa")))
    assert no_toggle.menu_expanded is False
    assert no_toggle.courses == []


def test_observed_at_is_preserved_in_provenance():
    when = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    result = discover_courses(
        _observe(_toggle(), _course_link("DEPT 100", "aaa"), observed_at=when)
    )
    assert result.courses[0].provenance.observed_at == when
