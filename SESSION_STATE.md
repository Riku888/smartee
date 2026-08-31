# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Assignment Extractor — v1 functionally complete.

## What works (verified against real captures, 5 courses)

`smartee/assignment/extract.py` → `extract_assignments()` over a recon
snapshot's `assignment_row_candidates`, producing per row:

- `title`, `due_at_utc` (verbatim `<time datetime>`), `due_local_text`,
  `due_timezone`
- `status_label` (`Submit` / `Completed` / `Closed` / …), `is_actionable`
- `points_possible`, `points_earned`, `grade_weight_percent`,
  `weighted_points_earned` (incl. weight-only `"0%"` ungraded cell)
- `description` (expanded rows — `#AssignmentDescription` body text),
  `resource_links`
- skips detail-panel / Exam-List candidates; dedups on (title, due);
  `is_assignment_list` from the `assignments_component_present` flag

Recon tooling: `datetime` attribute kept; row cap 150; component flag;
description-block text capture.

## Open (low priority — not blocking)

- **Stable per-assignment id** — behind the `Show Course Homework ID`
  toggle; located in the DOM, never activated in a capture. Dedup on
  (title, due) works fine meanwhile.
- Description text via the `#descriptionBlock` fallback carries panel
  chrome; `#AssignmentDescription` alone is cleaner (selector now tries it
  first — unverified on a fresh capture).
- Locked `Opens <date>` rows, pristine `Check off` row, `*`/`§` markers.
- Prioritizer / Combined Schedule / Grade Summary — cross-course pages,
  empty pre-semester; capture once the term starts (roadmap #3 input).

## Next candidates

1. Normalization: pair extracted rows with course context → deterministic
   `smartee.domain.models.Assignment` (synthetic id from course_id + title
   + due).
2. Roadmap #2 — Material Manifest.

## Operational state

On `main` (PRs #10–#13 merged). One open PR: `fix/description-selector-priority`.
