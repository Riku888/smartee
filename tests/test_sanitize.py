"""Deterministic tests for text-block sanitization.

Synthetic inputs only. `sanitize_text_block` is the multi-line sibling of
`sanitize_label`, used for untrusted course-authored blocks (assignment
descriptions) captured to local recon evidence.
"""

from smartee.resources import sanitize_text_block


def test_keeps_line_breaks_but_strips_other_control_chars():
    raw = "Line one\x00\x07\nLine two\ttab\x1b here"
    assert sanitize_text_block(raw) == "Line one\nLine two tab here"


def test_trims_each_line_and_drops_leading_trailing_blanks():
    raw = "\n\n   padded line   \n\n"
    assert sanitize_text_block(raw) == "padded line"


def test_collapses_runs_of_blank_lines_to_one():
    raw = "First para\n\n\n\n\nSecond para\n\n\n\nThird"
    assert sanitize_text_block(raw) == "First para\n\nSecond para\n\nThird"


def test_single_blank_line_between_paragraphs_is_preserved():
    raw = "First para\n\nSecond para"
    assert sanitize_text_block(raw) == "First para\n\nSecond para"


def test_length_is_capped_with_ellipsis():
    out = sanitize_text_block("x " * 5000, max_length=100)
    assert len(out) <= 101
    assert out.endswith("…")


def test_empty_input_returns_empty_string():
    assert sanitize_text_block("") == ""
    assert sanitize_text_block("\n\n   \n") == ""
