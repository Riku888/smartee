# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Roadmap #6 — Teacher (first LLM feature). Assignment → AI study note.
Roadmap #1–#3(pure) + #5 done; `scripts/build_vault.py --vault <path>`
runs the deterministic pipeline into the vault.

## Teacher / LLM (new)

- `smartee/llm/` — `generate(system, prompt, config=…)`, one-shot Anthropic
  call. Model is `SMARTEE_TEACHER_MODEL` → default `claude-opus-5`
  (D-022). Adaptive thinking. `LlmUnavailable` on missing SDK / creds /
  refusal — deterministic layers never touch this (Hard Rule 3).
- `smartee/teacher/` — `build_study_note(Assignment) -> StudyNote`.
  Pedagogical reconstruction (D-008), source facts vs AI enrichment kept
  separate (D-009); the untrusted description is passed inside an
  `<assignment_content>` block the system prompt names as inert data
  (Hard Rule 6). Sections: what it asks / concepts / approach / mistakes /
  check yourself / action.
- `smartee/obsidian/{render,vault}` — `render_study_note` /
  `write_study_note` → `02 Assignments/<title>.md`, `ai_generated: true`
  frontmatter + notice.
- `anthropic>=1.2` added to deps. `smartee/config.load_env` — minimal
  `.env` loader (no dep, does not override real env vars). `.env` at the
  repo root holds `ANTHROPIC_API_KEY` (present, gitignored).
- `scripts/build_vault.py --study-notes` loads `.env` and generates one
  study note per assignment **that has a captured description** into
  `02 Assignments/`. Ran for real: `claude-opus-5` produced a strong
  study note for the one described assignment (STEM fair). It is in the
  user's vault.
- `assemble_course_bundle` now **merges** duplicate assignments
  field-by-field (first-non-empty wins) so a description / due date seen
  in only one capture survives.
- `SMARTEE_TEACHER_MODEL=claude-sonnet-5` for ~5× cheaper.

The user's real vault: `/mnt/c/Users/rikut/OneDrive - Brigham Young
University/Documents/Smartee` (name "Smartee", OneDrive-synced). Notes were
written there for CYBER 467, IT&C 293, IT&C 366, ME EN 475.

Course identity in the CLI is the course-switcher label (the URL `cid-` is
unreliable — stale across "same URL, different DOM"); `course_id` is a
slug of that label. Old pre-`datetime` captures render with `Due: —`.

## Obsidian output

`smartee/obsidian/` — `render_course_overview(CourseBundle) -> str` (pure
Markdown: frontmatter + Summary + Assignments table + Materials table,
facts only, no pedagogy) and `write_course_overview(bundle, vault_dir)`
which writes `01 Courses/<course>/Course Overview.md` (filesystem adapter,
overwrites in place). Verified: a real 26-assignment course renders a
clean note. Teacher-generated concept/week notes (§14) are roadmap #6.

## Course bundle

`smartee/course/bundle.py` → `assemble_course_bundle(course_id=…,
assignments=…, materials=…)` → `CourseBundle`: dedup by id, drop
cross-course items, sort (assignments by due then title, materials by
name), plus a `CourseBundleSummary` (counts, graded, submission-pending,
materials-by-type). Pure — a Collector supplies the captures; this only
reconciles the already-normalized pieces. Verified end-to-end:
recon → extract → normalize → build_manifest → assemble (8 deduped
materials across 4 content pages; 26 assignments sorted by due).

Next: the Collector (Playwright navigation to feed the pipeline) — needs
the D-019 scaffolding (verifier / budget / stop / escalation), OR jump to
roadmap #5 Obsidian output which can consume a `CourseBundle` today.

## Material Manifest v1

`smartee/material/manifest.py` → `build_manifest(ContentPageObservation)`:
one captured content page's links → `list[MaterialManifestEntry]`. A link
is a material iff it is a Learning Suite file download
(`.../fileDownload.php?fileId=…`) or a cross-origin http(s) link to a
non-chrome host; in-app nav and site chrome dropped; dedup by `fileId`
(else URL hash). `name` is a typed placeholder when the link text is
generic ("Download") — real names resolve later at acquisition from the
HTTP response. Verified against the real 12-snapshot capture (e.g. a
"Lectures" page → 5 file materials; a lab page → 1 file + 1 Box link).

Deferred (not blocking, no capture needed now): enumerating every content
page of a course (roadmap #3 — some content pages *do* expose the
content-section `<a>` hrefs); the Schedule page's week/row structure;
per-material real filenames.

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
