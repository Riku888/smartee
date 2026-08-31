# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Phase 1 (vertical slice) is **complete**: recon captures → deterministic
pipeline → Obsidian vault, AI study notes per assignment with a captured
description, and a cross-course `00 Dashboard/Today.md` priority view.
Runs via `scripts/build_vault.py --vault <path> [--study-notes]`.

Phase 2 (Collector) has started — **assignments-only slice built, not yet
run live**. `scripts/collect_learning_suite.py`: after the human logs in,
it discovers courses from the switcher menu and captures each course's
assignments list, writing the same `recon-<ts>.json`. Needs one real
capture session to validate (does the switcher click expand the menu? do
the derived assignment URLs resolve?). Still to come in Phase 2: content
page nav (blocked on hrefless section links), material downloads, diff
detection.

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
- `smartee/planner/priority.py` — `rank_actionable(bundles, *, now,
  horizon_days=None)` → `list[RankedAssignment]`, most urgent first.
  Actionable = has a submission action and no score yet. Score =
  `0.7*urgency + 0.3*impact`; urgency is bucketed by days-to-due, impact
  is `grade_weight/100` (unknown → 0.3); overdue is a tier above
  everything on time. Deliberately simple and **provisional** — §16.1
  says don't let an LLM invent the weights, OPEN_QUESTIONS #9 stays open.
  Every ranked item carries its own numbers + a human `reason`.

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
- `render_today(ranked, generated_at)` / `write_today(ranked, vault_dir)`
  → `00 Dashboard/Today.md`: one cross-course table (priority, due,
  assignment link, course link, why), `type: dashboard` frontmatter.
- `smartee/obsidian/vault.py` — `write_course_overview` →
  `01 Courses/<course>/<course>.md` (folder-note pattern; deletes a stale
  `Course Overview.md`); `write_study_note` → `02 Assignments/<title>.md`;
  `write_today` → `00 Dashboard/Today.md`. Filesystem adapter, overwrites
  generated files in place, touches nothing else.
- `scripts/build_vault.py` — reads every `.local/recon/output/*.json`,
  runs the pipeline, writes one course note per course + `Today.md`;
  `--study-notes` loads `.env` and adds one study note per assignment with
  a description.

### Verified end to end (2026-08-31, real vault)

Vault: `/mnt/c/Users/rikut/OneDrive - Brigham Young University/Documents/
Smartee` (name "Smartee", OneDrive-synced). `build_vault.py --study-notes`
wrote 4 course notes + 3 Japanese deep study notes (CYBER 467 ×2, IT&C 293
×1) + `Today.md`. IT&C 366 / ME EN 475 have no captured assignment
descriptions yet, so no study notes for them. Graph connects each course
to its assignment notes.

`Today.md` ranked 22 actionable assignments: CYBER 467 (14 "Submit",
TryHackMe Registration at #1 — the real next deadline) + ME EN 475 (8
"Submit", all undated in the old capture, so score ≈ 0). IT&C 293 / 366
captures are from a finished-term state (all Completed/Closed, scored), so
nothing from them is actionable — correct.

Known vault-side wrinkle: clicking an unresolved `[[link]]` in Obsidian
creates the note at the "default location for new notes" (currently the
vault root), which will collide with the `02 Assignments/` file Smartee
generates later. Fix in Obsidian settings, not in code.

## Recon input

- `scripts/recon_learning_suite.py` — manual: headful Chromium + local
  persistent profile, manual BYU/Duo login, press Enter to capture the
  current page (read-only). Still the path for content / materials pages
  and any non-assignment page. Writes `.local/recon/output/recon-<ts>.json`.
- `scripts/collect_learning_suite.py` — **new, Collector v1**: same output
  format, but drives its own navigation. After login it clicks the
  course-switcher toggle (the only click it makes), runs `discover_courses`,
  then for each course `page.goto` the derived assignments URL and
  `capture_page`. Detects the login wall and pauses; hard budgets
  (`smartee/collector/plan.CollectionBudget` — max courses/pages/seconds,
  nav delay). Falls back to "open the menu yourself, press Enter" if the
  toggle click doesn't expand the menu. **Not yet run against the real
  site.**
- `smartee/collector/plan.py` (pure, tested): `assignments_url` (derive the
  list URL from a course-scoped URL the browser resolved to +
  the verified `student/home/assignments` tail), `classify_snapshot`
  (`assignments_list` / `exam_list` / `not_logged_in` / `other` — checks
  the capture, not the URL), `is_auth_wall`, `CollectionBudget`.

Course identity is still the course-switcher label; the URL `cid-` token is
unreliable across "same URL, different DOM". Old pre-`datetime` captures
render with `Due: —`.

## Open / deferred (not blocking)

- **Stable per-assignment id** — behind the `Show Course Homework ID`
  toggle; located in the DOM, never activated in a capture. **Abandoned**
  — (title, due) identifies all 5 courses / ~80 assignments fine. Do not
  ask for this capture again.
- Quiz / grade / discussion page DOM structure — never visited
  (`OPEN_QUESTIONS.md` #1).
- `Today.md` follow-ups: a `This Week.md` / `Semester.md` split (the
  `horizon_days` param already exists), and tuning the urgency/impact
  formula against real usage (OPEN_QUESTIONS #9). The undated ME EN 475
  tail sits at score ≈ 0 until a fresh capture gives it due dates.
- Learning Suite Combined Schedule / Grade Summary / Prioritizer pages —
  cross-course, empty pre-semester; capture once the term is live.
- Enumerating every content page of a course (some content pages expose
  the section `<a>` hrefs); Schedule page week/row structure;
  per-material real filenames (resolve at acquisition).
- **Collector live validation** — run `collect_learning_suite.py` once
  against the real site: does clicking the switcher toggle expand the
  menu (OBSERVATIONS: no `aria-controls`/handler was ever captured)? do
  the derived `student/home/assignments` URLs resolve for every course
  (one course uses a `/page/` path variant)? does the persistent profile
  keep the session between runs (OPEN_QUESTIONS #2)?

## Autonomy ladder (ARCHITECTURE §21, D-018/D-019)

Currently Level 1–2 (suggest / write generated notes the human reviews).
Unattended loops require verifier + budget + stop conditions + persistent
state + human escalation before going further. The Collector is a
navigation tool, not an unattended loop — it still ends in a human-run
`build_vault.py`.

## Operational state

`main` is at PR #30 (Today dashboard; #29 had merged into a stale base and
was re-landed as #30). Open PR: `feat/collector-assignments` — Collector
v1. Branch every PR off `main` — never stack a PR on another feature
branch (GitHub won't retarget it and it can merge into a dead branch).
