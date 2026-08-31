# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Material Manifest — evidence phase. Assignment Extractor v1 done
(extraction + normalization).

## Material Manifest — evidence so far

12-snapshot recon of 3 courses analysed (`docs/recon/OBSERVATIONS.md`
§ "Course navigation + content pages"). Content pages are
`student/pages/id-*`; downloadable materials are inline `<a>Download</a>`
with a `fileId` href but **no filename**; the content-section nav `<a>`
elements have **no href**. Two recon-tooling gaps block a first build:

1. Capture link `title` attribute + nearest heading/body-text context so a
   `Download` link's material can be identified.
2. Capture the content-section `<a>` elements' real attributes (or the
   content index page `student/pages`) to get the section→page mapping.

Next: enhance the recon tool for those two, then one more capture
(including the `Content` index), then design the manifest.

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

`smartee/assignment/normalize.py` → `normalize_assignments(rows, course_id=…)`
turns those into `smartee.domain.models.Assignment`: parses `due_at` to an
aware datetime, validates URLs, mints a stable synthetic id
(`"<course_id>:<hash of normalized title>"` — a moved deadline stays the
same assignment). Added `Assignment.status` (raw LS label). Verified
end-to-end: 26 real rows → 26 `Assignment` objects, unique stable ids.

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

1. Roadmap #2 — Material Manifest (needs recon of course content/materials
   pages first).
2. Course-traversal pass that calls discovery → per-course assignment
   extract+normalize.

## Operational state

On `main` (PRs #10–#14 merged). One open PR: `feat/assignment-normalize`.
