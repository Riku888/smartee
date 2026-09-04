"""Deterministic tests for the assignment-list extractor.

Synthetic inputs only — no real course ids, titles, dates, or captured DOM.
Row shapes mirror the two real read-only captures documented in
`docs/recon/OBSERVATIONS.md` § "Assignment-list row structure": a matched
status control plus a bounded container whose descendants carry the row's
cells at fixed path suffixes.
"""

from datetime import UTC, datetime

from smartee.assignment import AssignmentListObservation, extract_assignments
from smartee.assignment.extract import AssignmentRowObservation
from smartee.resources import (
    build_container_record,
    build_interactive_element_record,
    build_link_record,
    build_node_record,
)

_PAGE = "https://learningsuite.byu.edu/.r4C7/cid-0000/student/home/assignments"


def _control(label, *, tag="button", role_button=True):
    attrs = {"type": "button"}
    if role_button:
        attrs["role"] = "button"
        attrs["aria-label"] = label
    return build_interactive_element_record(
        tag, label, _PAGE, attributes=attrs, data_attributes={}
    )


def _desc(tag, path, text="", attrs=None):
    raw = {"tag": tag, "path": path, "text": text}
    if attrs:
        raw["attrs"] = attrs
    return raw


def _container(descendants, *, links=None):
    return build_container_record(
        build_node_record(
            "div", "border-b border-gray1", attributes={}, data_attributes={}
        ),
        descendants=descendants,
        links=links or [],
        interactive=[],
    )


def _row_descendants(
    *,
    title="Lab One",
    due_date_text="Sep 16",
    due_datetime="2026-09-16T19:00:00.000Z",
    local_time="1:00 pm",
    timezone="MDT",
    points_possible="1.0",
    points_earned=None,
    weight_cell="0 /4.17%",
):
    out = [_desc("span", "/div[1]/div[2]/span[1]", title)]
    if due_date_text is not None:
        time_attrs = {"datetime": due_datetime} if due_datetime is not None else None
        out.append(
            _desc("time", "/div[1]/div[3]/span[1]/time[1]", due_date_text, time_attrs)
        )
    if local_time is not None:
        out.append(_desc("time", "/div[1]/div[3]/span[1]/span[2]/time[1]", local_time))
    if timezone is not None:
        out.append(_desc("span", "/div[1]/div[3]/span[1]/span[2]/span[2]", timezone))
    if points_possible is not None:
        out.append(_desc("div", "/div[1]/div[5]/div[1]", points_possible))
    if points_earned is not None:
        out.append(_desc("b", "/div[1]/div[5]/div[1]/span[1]/b[1]", points_earned))
    if weight_cell is not None:
        out.append(_desc("div", "/div[1]/div[6]", weight_cell))
    return out


def _row(control=None, descendants=None, links=None, description_text=None):
    return AssignmentRowObservation(
        control=control if control is not None else _control("Submit"),
        container=_container(
            descendants if descendants is not None else _row_descendants(),
            links=links,
        ),
        description_text=description_text,
    )


def _observe(*rows, page_url=_PAGE, observed_at=None, component_present=None):
    return AssignmentListObservation(
        rows=list(rows),
        page_url=page_url,
        observed_at=observed_at,
        assignments_component_present=component_present,
    )


# --- current-term, ungraded (course A shape) -------------------------------


def test_submit_row_ungraded():
    at = datetime(2026, 8, 28, tzinfo=UTC)
    result = extract_assignments(_observe(_row(), observed_at=at))

    assert result.is_assignment_list is True
    (a,) = result.assignments
    assert a.title == "Lab One"
    assert a.due_at_utc == "2026-09-16T19:00:00.000Z"
    assert a.due_local_text == "1:00 pm"
    assert a.due_timezone == "MDT"
    assert a.status_label == "Submit"
    assert a.is_actionable is True
    assert a.points_possible == 1.0
    assert a.points_earned is None
    assert a.grade_weight_percent == 4.17
    assert a.weighted_points_earned == 0.0
    assert a.description is None
    assert a.resource_links == []
    assert a.provenance.observed_at == at
    assert a.provenance.page_domain == "learningsuite.byu.edu"


# --- past-term, graded (course B shape) -----------------------------------


def test_completed_row_graded_is_not_actionable():
    row = _row(
        control=_control("Completed", tag="div"),
        descendants=_row_descendants(
            title="Attend the Event",
            due_datetime="2026-01-29T15:00:00.000Z",
            local_time="8:00 am",
            timezone="MST",
            points_possible="2.0",
            points_earned="2.0",
            weight_cell="6.67 /6.67%",
        ),
    )
    (a,) = extract_assignments(_observe(row)).assignments

    assert a.status_label == "Completed"
    assert a.is_actionable is False
    assert a.points_possible == 2.0
    assert a.points_earned == 2.0
    assert a.weighted_points_earned == 6.67
    assert a.grade_weight_percent == 6.67


def test_view_submit_div_control_is_actionable():
    # A live CYBER 467 capture (2026-09-04) rendered "TryHackMe Registration"
    # with a <div role="button"> labelled "View/Submit" — an action, not a
    # terminal state, even though it is not a real <button>.
    row = _row(
        control=_control("View/Submit", tag="div"),
        descendants=_row_descendants(
            title="TryHackMe Registration",
            due_datetime="2026-09-09T19:00:00.000Z",
        ),
    )
    (a,) = extract_assignments(_observe(row)).assignments

    assert a.status_label == "View/Submit"
    assert a.is_actionable is True


def test_begin_lab_control_is_actionable():
    # CYBER 467 Labs (2026-09-04) render a <div role="button"> "Begin", not
    # "Submit" — ~16 such rows were dropped before "begin" was recognised.
    row = _row(
        control=_control("Begin", tag="div"),
        descendants=_row_descendants(
            title="Lab 3 - Enumeration",
            due_datetime="2026-10-07T05:59:00.000Z",
        ),
    )
    (a,) = extract_assignments(_observe(row)).assignments

    assert a.status_label == "Begin"
    assert a.is_actionable is True


def test_opens_later_row_is_extracted_but_not_actionable():
    row = _row(
        control=_control("Opens Oct 7", tag="div"),
        descendants=_row_descendants(
            title="Lab 5 - Privilege Escalation",
            due_datetime="2026-10-21T05:59:00.000Z",
        ),
    )
    (a,) = extract_assignments(_observe(row)).assignments

    assert a.title == "Lab 5 - Privilege Escalation"
    assert a.is_actionable is False


def test_closed_row_zero_earned():
    row = _row(
        control=_control("Closed", tag="div"),
        descendants=_row_descendants(
            points_possible="5.0", points_earned="0.0", weight_cell="0 /6.67%"
        ),
    )
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.status_label == "Closed"
    assert a.points_possible == 5.0
    assert a.points_earned == 0.0
    assert a.weighted_points_earned == 0.0
    assert a.grade_weight_percent == 6.67


def test_whole_percent_weight_cell():
    row = _row(descendants=_row_descendants(weight_cell="25 /25%"))
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.weighted_points_earned == 25.0
    assert a.grade_weight_percent == 25.0


def test_ungraded_row_weight_only_cell_and_empty_score():
    # A genuinely ungraded assignment: "0%" (no "/") and an empty score cell.
    row = _row(descendants=_row_descendants(points_possible="", weight_cell="0%"))
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.points_possible is None
    assert a.points_earned is None
    assert a.weighted_points_earned is None
    assert a.grade_weight_percent == 0.0


# --- skip rules ----------------------------------------------------------


def test_detail_panel_candidate_is_skipped():
    # An expanded-detail control: spans exist, but none at the title suffix.
    descendants = [
        _desc("span", "/div[1]/ul[1]/li[1]/span[1]", "Description"),
        _desc("span", "/div[1]/ul[1]/li[2]/span[1]", "Group"),
    ]
    row = _row(control=_control("Check off"), descendants=descendants)
    result = extract_assignments(_observe(row))
    assert result.assignments == []
    assert result.is_assignment_list is False


def test_exam_list_view_candidate_is_skipped():
    row = AssignmentRowObservation(control=_control("View"), container=_container([]))
    result = extract_assignments(_observe(row))
    assert result.assignments == []
    assert result.is_assignment_list is False


def test_container_none_is_skipped():
    row = AssignmentRowObservation(control=_control("Submit"), container=None)
    assert extract_assignments(_observe(row)).assignments == []


# --- is_assignment_list flag -----------------------------------------------


def test_component_flag_true_forces_is_assignment_list_even_with_no_rows():
    result = extract_assignments(_observe(component_present=True))
    assert result.is_assignment_list is True
    assert result.assignments == []


def test_component_flag_false_overrides_parsed_rows():
    result = extract_assignments(_observe(_row(), component_present=False))
    assert result.is_assignment_list is False
    assert len(result.assignments) == 1


def test_component_flag_none_falls_back_to_row_presence():
    assert extract_assignments(_observe(_row())).is_assignment_list is True
    assert extract_assignments(_observe()).is_assignment_list is False


# --- lenient parsing / missing data ------------------------------------


def test_missing_datetime_attr_yields_none_due_but_keeps_local_text():
    row = _row(descendants=_row_descendants(due_datetime=None))
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.due_at_utc is None
    assert a.due_local_text == "1:00 pm"


def test_missing_due_and_score_cells_are_none():
    row = _row(
        descendants=_row_descendants(
            due_date_text=None,
            local_time=None,
            timezone=None,
            points_possible=None,
            weight_cell=None,
        )
    )
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.title == "Lab One"
    assert a.due_at_utc is None
    assert a.due_local_text is None
    assert a.due_timezone is None
    assert a.points_possible is None
    assert a.grade_weight_percent is None
    assert a.weighted_points_earned is None


def test_non_numeric_cells_yield_none_without_raising():
    row = _row(descendants=_row_descendants(points_possible="—", weight_cell="n/a"))
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.points_possible is None
    # "n/a" has a "/": left "n" and right "a" both unparseable.
    assert a.weighted_points_earned is None
    assert a.grade_weight_percent is None


# --- dedup / provenance ------------------------------------------------


def test_duplicate_rows_deduped_on_title_and_due():
    result = extract_assignments(_observe(_row(), _row()))
    assert len(result.assignments) == 1


def test_same_title_different_due_kept_separately():
    r2 = _row(descendants=_row_descendants(due_datetime="2026-10-01T19:00:00.000Z"))
    result = extract_assignments(_observe(_row(), r2))
    assert len(result.assignments) == 2


def test_page_url_is_sanitized_in_provenance():
    dirty = _PAGE + "?sessionToken=abc123&ok=1"
    (a,) = extract_assignments(_observe(_row(), page_url=dirty)).assignments
    assert a.provenance.page_url is not None
    assert "sessionToken" not in a.provenance.page_url
    assert "abc123" not in a.provenance.page_url


def test_description_from_expanded_row_is_sanitized():
    row = _row(description_text="Read chapters 3-4.\n\n\n\nSubmit a one-page memo.")
    (a,) = extract_assignments(_observe(row)).assignments
    assert a.description == "Read chapters 3-4.\n\nSubmit a one-page memo."


def test_description_absent_is_none():
    assert extract_assignments(_observe(_row())).assignments[0].description is None
    blank = _row(description_text="   \n\n  ")
    assert extract_assignments(_observe(blank)).assignments[0].description is None


def test_resource_links_read_from_expanded_container():
    link = build_link_record(
        "Download",
        "https://learningsuite.byu.edu/x/plugins/Upload/fileDownload.php?fileId=abc",
        _PAGE,
    )
    (a,) = extract_assignments(_observe(_row(links=[link]))).assignments
    assert a.resource_links == [
        "https://learningsuite.byu.edu/x/plugins/Upload/fileDownload.php?fileId=abc"
    ]
