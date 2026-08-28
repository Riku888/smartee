# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Assignment Extractor — v1 (assignments-list rows) implemented and tested.

## Done

- Two read-only captures analysed (current-term ungraded course + past-term
  graded course); collapsed-row layout VERIFIED identical across both.
  Findings in `docs/recon/OBSERVATIONS.md` § "Assignment-list row structure".
- Recon tooling keeps the `datetime` structural attribute.
- `smartee/assignment/extract.py` — `extract_assignments()` over a recon
  snapshot's `assignment_row_candidates`: title, `due_at_utc` (verbatim
  `<time datetime>`), `due_local_text`, `due_timezone`, `status_label` /
  `is_actionable`, `points_possible`, `points_earned`, `grade_weight_percent`,
  `weighted_points_earned`, `resource_links`. Skips detail-panel and
  Exam-List candidates; dedups on (title, due). Verified end-to-end against
  both real captures. Tests in `tests/test_assignment_extract.py`.

## Deferred (need more evidence, not blocking)

- Stable per-assignment id — behind the `Show Course Homework ID` toggle
  (never expanded).
- Description **body text** — recon DOM walk stops before it
  (`#AssignmentDescription` came back empty); needs a walk-depth bump.
- Pristine unchecked `Check off` row; locked `Opens <date>` rows; the `*`
  superscript marker.

## Next candidates

Wire extraction into a course-level pass (pair rows with course context →
`smartee.domain.models.Assignment`), or the Material Manifest (roadmap #2).

## Operational state

Branch `feat/assignment-extractor`. Uncommitted: `datetime` recon patch,
`smartee/assignment/` + its tests, doc updates
(`docs/recon/OBSERVATIONS.md`, this file). 139 tests pass; ruff + ty clean.
