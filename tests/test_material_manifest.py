"""Deterministic tests for the content-page material manifest.

Synthetic links only — no real course ids, file ids, or captured DOM.
Links are built with the shared `build_link_record` so classification and
sanitization match production.
"""

from datetime import UTC, datetime

from smartee.domain.enums import AcquisitionStatus
from smartee.material import ContentPageObservation, build_manifest
from smartee.resources import build_link_record

_PAGE = "https://learningsuite.byu.edu/.x/cid-abc/student/pages/id-lectures"


def _download(file_id: str, text: str = "Download"):
    href = (
        "https://learningsuite.byu.edu/.x/cid-abc/student/pages"
        f"/plugins/Upload/fileDownload.php?fileId={file_id}"
    )
    return build_link_record(text, href, _PAGE)


def _link(text: str, href: str):
    return build_link_record(text, href, _PAGE)


def _observe(*links, course_id="cid-abc", observed_at=None):
    return ContentPageObservation(
        links=list(links),
        page_url=_PAGE,
        course_id=course_id,
        observed_at=observed_at,
    )


# --- what counts as a material ----------------------------------------


def test_file_download_becomes_a_material():
    at = datetime(2026, 8, 31, tzinfo=UTC)
    (m,) = build_manifest(_observe(_download("f-1"), observed_at=at))
    assert m.id == "cid-abc:file:f-1"
    assert m.course_id == "cid-abc"
    assert m.material_type == "learning_suite_file"
    assert m.status is AcquisitionStatus.DISCOVERED
    assert str(m.source_url).endswith("fileId=f-1")
    assert m.discovered_at == at


def test_cross_origin_links_are_materials_by_type():
    entries = build_manifest(
        _observe(
            _link("", "https://byu.box.com/s/abc123"),
            _link("", "https://youtu.be/xyz"),
            _link("Reading", "https://example.com/article"),
            _link("", "https://example.com/notes.pdf"),
        )
    )
    assert [e.material_type for e in entries] == [
        "box_file",
        "youtube_video",
        "external_link",
        "document",
    ]


def test_same_origin_navigation_is_dropped():
    entries = build_manifest(
        _observe(
            _link("Home", "/.x/cid-abc/student/home"),
            _link("Content", "/.x/cid-abc/student/pages"),
            _link("Syllabus", "/.x/cid-abc/student/syllabus"),
            _link("Week 2", "/.x/cid-abc/student/pages/id-week2"),
        )
    )
    assert entries == []


def test_chrome_hosts_are_dropped():
    entries = build_manifest(
        _observe(
            _link("LS Help", "https://softwaresupport.byu.edu/learning-suite/student"),
            _link("", "https://learnanywhere.byu.edu"),
        )
    )
    assert entries == []


def test_non_http_and_empty_hrefs_are_dropped():
    entries = build_manifest(
        _observe(
            _link("mail", "mailto:prof@byu.edu"),
            _link("js", "javascript:void(0)"),
            _link("nothing", ""),
        )
    )
    assert entries == []


# --- identity / dedup ------------------------------------------------


def test_same_file_linked_twice_is_one_entry():
    entries = build_manifest(_observe(_download("f-9"), _download("f-9", text="here")))
    assert len(entries) == 1


def test_distinct_files_and_links_keep_page_order():
    entries = build_manifest(
        _observe(
            _download("f-1"),
            _link("Video", "https://youtu.be/a"),
            _download("f-2"),
        )
    )
    assert [e.id for e in entries] == [
        "cid-abc:file:f-1",
        entries[1].id,
        "cid-abc:file:f-2",
    ]
    assert entries[1].id.startswith("cid-abc:link:")


def test_identity_includes_course_id():
    a = build_manifest(_observe(_download("f-1"), course_id="c1"))[0]
    b = build_manifest(_observe(_download("f-1"), course_id="c2"))[0]
    assert a.id != b.id


# --- names ----------------------------------------------------------


def test_generic_link_text_becomes_a_typed_placeholder():
    (m,) = build_manifest(_observe(_download("f-1", text="Download")))
    assert m.name == "Learning Suite file"


def test_meaningful_link_text_is_kept_as_name():
    (m,) = build_manifest(
        _observe(_link("Kerberos primer (PDF)", "https://example.com/kerb.pdf"))
    )
    assert m.name == "Kerberos primer (PDF)"
