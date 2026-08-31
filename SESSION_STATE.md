# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Roadmap #6 — Teacher (first LLM feature) — is **working end to end**:
recon captures → deterministic pipeline → Obsidian vault, plus AI study
notes per assignment that has a captured description. Runs via
`scripts/build_vault.py --vault <path> [--study-notes]`.

Next: the **Collector** (roadmap toward #3/#12) — Playwright navigation
that produces the recon JSON automatically instead of the manual
`scripts/recon_learning_suite.py` press-Enter loop.

## Deterministic pipeline (verified against real captures, 5 courses)

- `smartee/assignment/extract.py` — `extract_assignments()` over a recon
  snapshot's `assignment_row_candidates`: per row `title`, `due_at_utc`
  (verbatim `<time datetime>`), `due_local_text`, `due_timezone`,
  `status_label` / `is_actionable`, points/weight cells (incl. weight-only
  `"0%"` ungraded cell), `description` (expanded rows), `resource_links`.
  Skips detail-panel / Exam-List candidates; dedups on (title, due).
- `smartee/assignment/normalize.py` — `normalize_assignments(rows,
  course_id=…)` → `smartee.domain.models.Assignment`: aware `due_at`,
  validated URLs, stable synthetic id `"<course_id>:<hash of normalized
  title>"` (a moved deadline stays the same assignment), raw `status`.
- `smartee/material/manifest.py` — `build_manifest(ContentPageObservation)`:
  one content page's links → `list[MaterialManifestEntry]`. Material iff
  LS file download (`fileDownload.php?fileId=…`) or cross-origin http(s)
  to a non-chrome host. Dedup by `fileId` else URL hash; typed placeholder
  name when link text is generic.
- `smartee/course/bundle.py` — `assemble_course_bundle(course_id=…,
  course_label=…, assignments=…, materials=…)` → `CourseBundle`: dedup by
  id, drop cross-course items, sort, **merge** duplicate assignments
  field-by-field (first-non-empty wins) so a description/due seen in only
  one capture survives, plus a `CourseBundleSummary`.
- `smartee/course/discovery.py` / `entry.py` — deterministic course
  enumeration from an expanded course-switcher menu, and course-entry
  href resolution. Not yet driven by anything (the Collector will).

## Teacher / LLM

- `smartee/llm/` — `generate(system, prompt, config=…)`, one-shot
  Anthropic call, adaptive thinking. Model `SMARTEE_TEACHER_MODEL` →
  default `claude-opus-5` (D-022). `LlmUnavailable` on missing SDK / creds
  / refusal — the deterministic layers never touch this (Hard Rule 3).
- `smartee/teacher/study_note.py` — `build_study_note(Assignment, *,
  course_label=…, language=…) -> StudyNote`. Deep pedagogical
  reconstruction (D-008): teaches every concept the assignment relies on,
  gives the method with rationale, and works **one complete example on
  invented data** — never the student's graded deliverable (Hard Rule 4).
  Seven sections, headings are the contract, per-language (`en` / `ja`).
  The untrusted description rides inside an `<assignment_content>` block
  the system prompt names as inert data (Hard Rule 6). Source facts vs.
  AI enrichment kept separate (D-009).
- `smartee/config.py` — `load_env` (minimal `.env` loader, no dep, does
  not override real env vars). `.env` at repo root holds
  `ANTHROPIC_API_KEY` and `SMARTEE_NOTE_LANGUAGE` (present, gitignored).
  `SMARTEE_NOTE_LANGUAGE=ja` currently set → notes generate in Japanese.

## Obsidian output

- `smartee/obsidian/render.py` — pure `CourseBundle` → Markdown
  (`render_course_overview`, facts only, no pedagogy) and `StudyNote` →
  Markdown (`render_study_note`, `ai_generated: true` frontmatter +
  notice). The overview's assignment table links each row to its study
  note (`[[stem\|title]]`, unresolved until the note exists); the study
  note's frontmatter back-links `course: "[[<course folder note>]]"`.
- `smartee/obsidian/naming.py` — `course_stem` / `safe_stem`: one place
  that maps a title to its filename and its wikilink target so they match.
- `smartee/obsidian/vault.py` — `write_course_overview` →
  `01 Courses/<course>/<course>.md` (folder-note pattern; deletes a stale
  `Course Overview.md`); `write_study_note` → `02 Assignments/<title>.md`.
  Filesystem adapter, overwrites generated files in place, touches nothing
  else.
- `scripts/build_vault.py` — reads every `.local/recon/output/*.json`,
  runs the pipeline, writes one course note per course; `--study-notes`
  loads `.env` and adds one study note per assignment with a description.

### Verified end to end (2026-08-31, real vault)

Vault: `/mnt/c/Users/rikut/OneDrive - Brigham Young University/Documents/
Smartee` (name "Smartee", OneDrive-synced). `build_vault.py --study-notes`
wrote 4 course notes + 3 Japanese deep study notes (CYBER 467 ×2, IT&C 293
×1). IT&C 366 / ME EN 475 have no captured assignment descriptions yet, so
no study notes for them. Graph connects each course to its assignment
notes.

Known vault-side wrinkle: clicking an unresolved `[[link]]` in Obsidian
creates the note at the "default location for new notes" (currently the
vault root), which will collide with the `02 Assignments/` file Smartee
generates later. Fix in Obsidian settings, not in code.

## Recon (manual, current input)

`scripts/recon_learning_suite.py` — headful Chromium + local persistent
profile, manual BYU/Duo login, press Enter to capture the current page
(read-only: never clicks/submits/fills). Writes each capture immediately
to `.local/recon/output/recon-<ts>.json`. Course identity comes from the
course-switcher label (`aria-label` "Show course selection menu. Current
course: …"); the URL `cid-` token is unreliable across "same URL,
different DOM". Old pre-`datetime` captures render with `Due: —`.

## Open / deferred (not blocking)

- **Stable per-assignment id** — behind the `Show Course Homework ID`
  toggle; located in the DOM, never activated in a capture. **Abandoned**
  — (title, due) identifies all 5 courses / ~80 assignments fine. Do not
  ask for this capture again.
- Quiz / grade / discussion page DOM structure — never visited
  (`OPEN_QUESTIONS.md` #1).
- Prioritizer / Combined Schedule / Grade Summary — cross-course pages,
  empty pre-semester; capture once the term is live.
- Enumerating every content page of a course (some content pages expose
  the section `<a>` hrefs); Schedule page week/row structure;
  per-material real filenames (resolve at acquisition).

## Autonomy ladder (ARCHITECTURE §21, D-018/D-019)

Currently Level 1–2 (suggest / write generated notes the human reviews).
Unattended loops require verifier + budget + stop conditions + persistent
state + human escalation before going further. The Collector is a
navigation tool, not an unattended loop — it still ends in a human-run
`build_vault.py`.

## Operational state

On `main` at PR #27 (deep study notes + course/note linking). No open
PRs. Working branch: `docs/post-27-cleanup`.
