"""Render a `CourseBundle` into a deterministic Obsidian note.

This is the v1 human-facing output (D-003): a single "Course Overview" note
per course with the *facts* — assignment list, due dates, status, points,
grade weight, and the material inventory. No pedagogy, no summarization, no
LLM: that is the Teacher Agent's job (ARCHITECTURE §14) and produces
separate concept / week notes later.

Pure: `CourseBundle` in, Markdown string out. The vault write lives in
`smartee.obsidian.vault`.
"""

from datetime import datetime

from smartee.course.bundle import CourseBundle
from smartee.domain.models import Assignment, MaterialManifestEntry
from smartee.obsidian.naming import course_stem, safe_stem
from smartee.planner import RankedAssignment
from smartee.teacher import StudyNote

_GENERATED_NOTICE = (
    "> Auto-generated from Learning Suite reconnaissance. Facts only — "
    "regenerated on each run, safe to leave untouched."
)

_STUDY_NOTE_NOTICE = {
    "en": (
        "> AI-generated study aid — not course material. The assignment's "
        "facts (due date, points, weight) live in the Course Overview; this "
        "note teaches the concepts and works a practice example on invented "
        "data, and may be wrong. It is not your graded deliverable."
    ),
    "ja": (
        "> AI が生成した学習補助であり、コース教材ではありません。締切・点数・"
        "重みは Course Overview が正。このノートは概念を解説し、架空データで"
        "練習例を解くもので、間違っている可能性があります。あなたの提出物では"
        "ありません。"
    ),
}


def render_course_overview(bundle: CourseBundle) -> str:
    """Full Markdown for `01 Courses/<course>/Course Overview.md`."""
    title = bundle.course_label or bundle.course_id
    lines = [
        _frontmatter(bundle),
        f"# {title}",
        "",
        _GENERATED_NOTICE,
        "",
        _summary_section(bundle),
        "",
        _assignments_section(bundle.assignments),
        "",
        _materials_section(bundle.materials),
        "",
    ]
    return "\n".join(lines)


def _frontmatter(bundle: CourseBundle) -> str:
    s = bundle.summary
    rows = {
        "type": "course-overview",
        "generated": "true",
        "course_id": bundle.course_id,
        "course": _yaml_scalar(bundle.course_label),
        "updated": _iso(bundle.assembled_at),
        "assignments": s.assignment_count,
        "materials": s.material_count,
        "graded_assignments": s.graded_assignment_count,
        "submissions_pending": s.submission_pending_count,
    }
    body = "\n".join(f"{key}: {value}" for key, value in rows.items())
    return f"---\n{body}\n---\n"


def _summary_section(bundle: CourseBundle) -> str:
    s = bundle.summary
    by_type = ", ".join(
        f"{count} {name}" for name, count in s.materials_by_type.items()
    )
    assignments_line = (
        f"- Assignments: {s.assignment_count} "
        f"({s.graded_assignment_count} graded, "
        f"{s.submission_pending_count} awaiting submission)"
    )
    materials_suffix = f" — {by_type}" if by_type else ""
    materials_line = f"- Materials: {s.material_count}{materials_suffix}"
    return f"## Summary\n\n{assignments_line}\n{materials_line}"


def _assignments_section(assignments: list[Assignment]) -> str:
    if not assignments:
        return "## Assignments\n\n_None found._"
    header = (
        "| Due (UTC) | Assignment | Status | Score | Weight |\n|---|---|---|---|---|"
    )
    rows = [
        "| {due} | {title} | {status} | {score} | {weight} |".format(
            due=_due(a.due_at),
            title=_assignment_link(a.title),
            status=_cell(a.status or "—"),
            score=_score(a.score, a.max_points),
            weight=_percent(a.grade_weight),
        )
        for a in assignments
    ]
    return "\n".join(["## Assignments", "", header, *rows])


def _assignment_link(title: str) -> str:
    """A table-cell link to the assignment's study note (which may not exist
    yet — an unresolved link still connects them in the graph once it does)."""
    stem = safe_stem(title, fallback=title)
    display = _cell(title)
    return f"[[{stem}\\|{display}]]" if stem else display


def _materials_section(materials: list[MaterialManifestEntry]) -> str:
    if not materials:
        return "## Materials\n\n_None found._"
    header = "| Material | Type | Status | Link |\n|---|---|---|---|"
    rows = [
        "| {name} | {mtype} | {status} | {link} |".format(
            name=_cell(m.name),
            mtype=_cell(m.material_type or "—"),
            status=_cell(m.status.value),
            link=f"[open]({m.source_url})" if m.source_url else "—",
        )
        for m in materials
    ]
    return "\n".join(["## Materials", "", header, *rows])


def render_study_note(note: StudyNote) -> str:
    """Full Markdown for `02 Assignments/<title>.md` — an AI-generated study
    note wrapped with provenance frontmatter and an "AI-generated" notice."""
    course_note = course_stem(note.course_label, note.course_id)
    frontmatter = "\n".join(
        [
            "---",
            "type: study-note",
            "ai_generated: true",
            f'course: "[[{course_note}]]"',
            f"assignment_id: {note.assignment_id}",
            f"course_id: {note.course_id}",
            f"model: {note.model}",
            f"language: {note.language}",
            f"generated: {_iso(note.generated_at)}",
            "---",
        ]
    )
    notice = _STUDY_NOTE_NOTICE.get(note.language, _STUDY_NOTE_NOTICE["en"])
    return "\n".join(
        [
            frontmatter,
            "",
            f"# {note.title}",
            "",
            notice,
            "",
            note.markdown.strip(),
            "",
        ]
    )


_TODAY_NOTICE = (
    "> Auto-generated priority view across all courses. Ranked by deadline "
    "urgency and grade weight — a provisional formula, regenerated on each "
    "run. Only assignments that still need submitting appear here."
)


def render_today(ranked: list[RankedAssignment], generated_at: datetime | None) -> str:
    """Full Markdown for `00 Dashboard/Today.md` — one cross-course table of
    the student's actionable assignments, most urgent first."""
    frontmatter = "\n".join(
        [
            "---",
            "type: dashboard",
            "generated: true",
            f"updated: {_iso(generated_at)}",
            f"actionable: {len(ranked)}",
            "---",
        ]
    )
    lines = [
        frontmatter,
        "",
        "# Today",
        "",
        _TODAY_NOTICE,
        "",
        _today_table(ranked),
        "",
    ]
    return "\n".join(lines)


def _today_table(ranked: list[RankedAssignment]) -> str:
    if not ranked:
        return "_Nothing actionable — every assignment with a submission is done._"
    header = (
        "| # | Priority | Due (UTC) | Assignment | Course | Why |\n"
        "|---|---|---|---|---|---|"
    )
    rows = [_today_row(i, r) for i, r in enumerate(ranked, start=1)]
    return "\n".join([header, *rows])


def _today_row(n: int, r: RankedAssignment) -> str:
    cells = [
        str(n),
        f"{r.score:.2f}",
        _due(r.assignment.due_at),
        _assignment_link(r.assignment.title),
        _course_link(r.course_label, r.course_id),
        _cell(r.reason),
    ]
    return "| " + " | ".join(cells) + " |"


def _course_link(label: str | None, course_id: str) -> str:
    stem = course_stem(label, course_id)
    return f"[[{stem}\\|{_cell(label or course_id)}]]"


# --- formatting helpers -------------------------------------------------


def _cell(text: str) -> str:
    """Inert one-line table cell: escape pipes, collapse whitespace."""
    return " ".join(text.split()).replace("|", "\\|") or "—"


def _due(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else "null"


def _score(score: float | None, max_points: float | None) -> str:
    if score is None and max_points is None:
        return "—"
    return f"{_num(score)} / {_num(max_points)}"


def _percent(value: float | None) -> str:
    return f"{_num(value)}%" if value is not None else "—"


def _num(value: float | None) -> str:
    if value is None:
        return "—"
    return str(int(value)) if value == int(value) else str(value)


def _yaml_scalar(value: str | None) -> str:
    if value is None:
        return "null"
    return f'"{value}"' if any(c in value for c in ':#"') else value
