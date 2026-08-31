"""Deterministic tests for the Collector's between-navigation decisions."""

import pytest

from smartee.collector import plan
from smartee.collector.plan import (
    SNAPSHOT_ASSIGNMENTS_LIST,
    SNAPSHOT_EXAM_LIST,
    SNAPSHOT_NOT_LOGGED_IN,
    SNAPSHOT_OTHER,
    CollectionBudget,
    assignments_url,
    classify_snapshot,
    is_auth_wall,
)

_DASHBOARD = "https://learningsuite.byu.edu/.MjTJ/student/cid--tQDtJf5AeQC/student/home/dashboard"
_ASSIGNMENTS = "https://learningsuite.byu.edu/.MjTJ/student/cid--tQDtJf5AeQC/student/home/assignments"


class TestIsAuthWall:
    @pytest.mark.parametrize(
        "url",
        [
            "https://cas.byu.edu/cas/login?service=x",
            "https://byu.okta.com/app/foo",
            "https://learningsuite.byu.edu/cas/login",
            "https://login.byu.edu/",
        ],
    )
    def test_login_urls_are_walls(self, url):
        assert is_auth_wall(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            _DASHBOARD,
            "https://learningsuite.byu.edu/student/home/assignments",
            "not a url",
            "",
        ],
    )
    def test_learning_suite_and_junk_are_not_walls(self, url):
        assert is_auth_wall(url) is False


class TestAssignmentsUrl:
    def test_derives_from_dashboard_url(self):
        assert assignments_url(_DASHBOARD) == _ASSIGNMENTS

    def test_already_assignments_url_is_unchanged(self):
        assert assignments_url(_ASSIGNMENTS) == _ASSIGNMENTS

    def test_works_without_a_session_segment(self):
        url = "https://learningsuite.byu.edu/student/cid-ABC123/student/home/x"
        assert assignments_url(url) == (
            "https://learningsuite.byu.edu/student/cid-ABC123/student/home/assignments"
        )

    def test_strips_query_and_fragment(self):
        assert assignments_url(_DASHBOARD + "?tab=1#top") == _ASSIGNMENTS

    @pytest.mark.parametrize(
        "url",
        [
            "https://learningsuite.byu.edu/student/home/assignments",  # no cid
            "https://cas.byu.edu/cas/cid-4gdhG4DvClCX/student/home/assignments",  # cid not under /student/
            "/student/cid-ABC/student/home/dashboard",  # not absolute
            "",
        ],
    )
    def test_returns_none_when_not_course_scoped(self, url):
        assert assignments_url(url) is None


class TestClassifySnapshot:
    def test_assignments_component_present(self):
        assert classify_snapshot({"assignments_component_present": True}) == (
            SNAPSHOT_ASSIGNMENTS_LIST
        )

    def test_exam_list_heading(self):
        snap = {
            "assignments_component_present": False,
            "headings": [{"level": "h1", "text": "  Exam List "}],
        }
        assert classify_snapshot(snap) == SNAPSHOT_EXAM_LIST

    def test_auth_wall_url_wins_over_component(self):
        snap = {
            "url": "https://cas.byu.edu/cas/login",
            "assignments_component_present": True,
        }
        assert classify_snapshot(snap) == SNAPSHOT_NOT_LOGGED_IN

    def test_unrecognized_is_other(self):
        assert classify_snapshot({"headings": [{"text": "Something else"}]}) == (
            SNAPSHOT_OTHER
        )

    def test_missing_keys_is_other(self):
        assert classify_snapshot({}) == SNAPSHOT_OTHER


class TestCollectionBudget:
    def test_deadline_from(self):
        assert CollectionBudget(max_seconds=60).deadline_from(1000.0) == 1060.0

    def test_exhausted_reports_each_limit(self):
        b = CollectionBudget(max_courses=3, max_pages=5, max_seconds=100)
        assert b.exhausted(pages=5, courses=0, now=0, deadline=100) is not None
        assert b.exhausted(pages=0, courses=3, now=0, deadline=100) is not None
        assert b.exhausted(pages=0, courses=0, now=100, deadline=100) is not None
        assert b.exhausted(pages=0, courses=0, now=1, deadline=100) is None

    def test_sleep_between_navigations_respects_zero_delay(self, monkeypatch):
        called = []
        monkeypatch.setattr(plan.time, "sleep", lambda s: called.append(s))
        plan.sleep_between_navigations(CollectionBudget(nav_delay_seconds=0))
        assert called == []
        plan.sleep_between_navigations(CollectionBudget(nav_delay_seconds=1.5))
        assert called == [1.5]
