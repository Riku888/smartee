# Learning Suite Recon Observations

Source: 20 read-only DOM snapshots captured with `scripts/recon_learning_suite.py`
across 4 distinct courses, one authentication flow, and repeat visits to the
same URLs, plus a later 10-snapshot set focused on one course's assignments
list (see "Assignment-list row structure" below). Raw capture JSON stays local
(`.local/recon/output/`, gitignored) and is never quoted here — this file
contains only sanitized structural findings. No course names, course codes,
headings text, file names, assignment titles, or account/profile identifiers
from the captures are reproduced below, since several captured headings, button
labels, assignment titles, and a linked filename were personally identifying or
course-private (Hard Rule 6 / `SECURITY.md`).

Everything marked **VERIFIED** was directly observed in the captures.
Everything marked **UNKNOWN** was not exercised by this capture set.

## Recurring Learning Suite patterns (VERIFIED)

- Same URL, different visible DOM: multiple captures at the *identical*
  `student/home/assignments` URL (across two different courses) returned
  completely different heading/button sets from one capture to the next —
  in one capture an assignment list with several "Submit"/"Check off"
  buttons, in another capture (same URL) a single heading with no
  assignment buttons at all. The same behavior was seen on a
  `student/pages/id-*` URL captured 5 times, where 4 captures returned an
  identical small DOM and the 5th (same URL) returned substantially more
  headings and links.
  - Conclusion: Learning Suite is client-rendered and does not always
    change the URL when the visible content changes (e.g. switching a
    tab/sub-view or expanding a section). **A stable URL is not a
    reliable proxy for "the same content" in this app.** UNKNOWN: the
    exact user action that triggers the content swap (tab click, lazy
    load, expand/collapse) — not captured.
- Every page captured used the same page `<title>` ("BYU Learning Suite")
  regardless of course or sub-page — title text is not usable to
  distinguish page type or course.
- Heading structure is shallow and inconsistent: most captured pages had
  exactly one heading (`h1`–`h6` combined), while a couple had 4 or up to
  11. Heading level/count is not a reliable page-type signal on its own.
- A large majority of `<a href>` elements on every page (about 3 in 4
  links, 498 of 634 total across all captures) sanitize to no domain and
  no usable href at all.
  - Conclusion (from code + data, not invented): `sanitize_url`/
    `classify_source_type` require an absolute URL with a scheme and
    host; they classify anything else — a relative in-app path, `#`,
    empty, or `javascript:`-style href — as `unknown`/`None`. Since the
    LEARNING_SUITE source type never appeared even once across 634 links,
    internal Learning Suite navigation almost certainly uses relative
    URLs rather than absolute `https://learningsuite.byu.edu/...` hrefs.
    UNKNOWN: the exact raw href strings, since only the sanitized/derived
    fields are persisted — we cannot distinguish "relative path" from
    "`#`" from "`javascript:void(0)`" after the fact.

## Differences across courses (VERIFIED / UNKNOWN)

- All 4 courses share the same base path shape:
  `/.-ZL-/cid-<opaque-course-id>/student/...`.
- 3 of 4 courses used `student/pages/id-<token>` for a content page; the
  4th course used `student/pages/page/id-<token>` (note the extra
  `/page/` segment). This is a real, directly observed path-shape
  difference between courses, not a typo in one capture — all 4 snapshots
  for that course used the double-segment form.
  - UNKNOWN: whether this reflects two different Learning Suite content
    types (e.g. a different "page" feature/template) or is coincidental
    to how the user navigated. Only one page was captured per URL
    pattern in most cases, so it can't be generalized.
- Only one course's captures included a `student/syllabus/course` URL.
  This does **not** mean other courses lack a syllabus route — it only
  means the syllabus page wasn't visited for the other 3 courses in this
  session. Presence/absence of routes per course is UNKNOWN beyond what
  was actually visited.

## Assignment patterns (VERIFIED)

- An assignments-list view renders one action button per assignment row;
  observed button labels were exactly: `Submit`, `View`, `View/Submit`,
  `Completed`, `Closed`, `Feedback`, `Check off`. These are read as plain
  visible text/value — no click was performed on any of them (Hard Rule 4:
  no submission was or will be implemented).
- The same assignments URL can also render a single-assignment detail
  view instead of the list (see "same URL, different DOM" above) — so an
  assignment detail is not guaranteed to live at its own distinct URL.
- A course-switcher control renders one button per enrolled course,
  labeled with (term, course code, course title) as visible text. Content
  redacted here as course-identifying/personal; structure only is
  reported.

## Assignment-list row structure (VERIFIED — two courses, two instructors)

Source: 15 read-only snapshots across two courses' assignments lists
(`student/home` and `student/home/assignments`) — one current-term course
(all rows `Submit`, nothing graded) and one past-term course (rows
`Completed` / `Closed`, graded), including snapshots with one row expanded.
Structure only; all titles/dates/scores below are illustrative
placeholders, not captured values. The positional layout below was
identical in both courses.

- The list is contained in `div#assignmentsComponent` (inside
  `#mainContent > #mainPage > #fullLSPage`). The Exam List view can render
  at the *same* `student/home/assignments` URL with **no**
  `#assignmentsComponent` ancestor and an `Exam List` heading and per-row
  `View` buttons — another instance of "same URL, different DOM". Presence
  of `#assignmentsComponent` is the structural signal for "assignments
  list is what's rendered".
- Inside `#assignmentsComponent`: a controls block containing a
  `Show Course Homework ID` toggle (`aria-expanded="false"` by default —
  UNKNOWN what it reveals when expanded; likely the stable per-assignment
  identifier that is otherwise absent, see below); then a **column-header
  row** with the labels `Title`, `Due`, `Submission`, `Score`,
  `% of Grade`, `Statistics` (preceded by an empty icon column); then the
  rows, **grouped under category headers** (e.g. a `Homework` header
  showing that category's `100%` weight).
- Each row is a `div.border-b.border-gray1`. It carries **no `id`, no
  `data-assignment-*`** — every `data-v-*` is an empty Vue scoped-style
  marker. There is no per-assignment stable identifier in the row, and no
  assignment-detail URL. Row identity is only (title text + due datetime +
  list position).
- Within a row the fields are **positional** (matching the column
  headers above), not class- or attribute-labeled. Paths are relative to
  the row's inner `div[1]` wrapper:
  - `…/div[2]/span[1]` — title, plain text.
  - `…/div[2]/span[2]/sup[1]/span[1]` — a `*` superscript on some rows.
    Meaning UNKNOWN.
  - `…/div[3]//time[1]` — due **date**. Its `datetime` attribute is an
    absolute UTC ISO timestamp (e.g. `2026-11-15T06:59:00.000Z`) and is
    authoritative: the element's visible text is a *local* date and can
    differ from the UTC date by a day. `datetime` is now captured
    (added to the recon structural-attribute allowlist).
  - `…/div[3]//span[2]/time[1]` — due **time**, local, visible text only
    (e.g. `11:59 pm`), no `datetime` attribute.
  - `…/div[3]//span[2]/span[2]` — timezone abbreviation text (`MST` /
    `MDT` observed).
  - `…/div[4]/div[1]/(button|div)[1]` — the row action/status control:
    `role="button"` with `aria-label` equal to the status word; the
    visible label repeats in a child `div`. An actionable state renders
    as `<button>` (`Submit`); a non-actionable state renders as `<div>`
    (`Completed`, `Closed`). Status words observed across both courses:
    `Submit`, `Completed`, `Closed` (and, from the earlier capture set,
    `View`, `View/Submit`, `Feedback`, `Check off`).
  - `…/div[5]/div[1]` — score cell. Graded rows: the cell's own text is
    the **points possible** (e.g. `5.0`), a nested `<b>` is the **points
    earned** (e.g. `0.0`), and a sibling `span` holds the `/` separator.
    Ungraded rows: no `<b>`, just the points-possible text and `/`.
  - `…/div[6]` — usually `earned /weight%`, e.g. `0 /6.67%` (nothing
    earned) or `6.67 /6.67%` (full credit): weighted points earned toward
    the final grade, then the assignment's grade **weight** as a percent.
    A genuinely ungraded assignment showed just `0%` here (no `/`, and an
    empty `…/div[5]/div[1]` score cell) alongside a `(Ungraded)` marker in
    `…/div[2]/span[2]`.
  - `…/div[7]/div[1]/i[2]` — a per-row `Statistics` control
    (`<i role="img" aria-label="Statistics">`).
  - A `sup` superscript after the title (`…/div[2]/span[N]/sup[1]/span[1]`)
    can hold `*` or `§`; meanings UNKNOWN.
- Expanding a row renders an extra `div[2]` **nested inside that same
  `div.border-b.border-gray1` container** — so an expanded detail maps to
  its row by DOM containment, deterministically, with no identifier
  needed. The detail subtree contains:
  - `ul > li#descriptionTab` ("Description"), `li#groupTab` ("Group"),
    and a third unlabeled `li`.
  - `div#descriptionBlock > div#AssignmentDescription` — the description
    body; a `Due:` label appears here too.
  - Its own `<button type="button">` controls whose label text
    (`Check off`, `Submit`) sits in a child `div` — structurally distinct
    from the list-row `role="button"` + `aria-label` control.
  - Any resource link (observed: a `Download` `<a>` →
    `…/plugins/Upload/fileDownload.php?fileId=<opaque>`, classified
    `learning_suite`, same-origin) sits inside this subtree, so resource
    links can be scoped to the expanded assignment.
  - `descriptionTab` / `groupTab` / `descriptionBlock` /
    `AssignmentDescription` are **singleton ids** — reused, so only one
    row is expandable at a time; they are not per-assignment identifiers.
- The dashboard (`student/home`) also lists rows with the same structure,
  plus locked/future rows whose control is a `div` (no `aria-label`) with
  text like `Opens Sep 2`. The recon row matcher keys on a fixed set of
  action words and does **not** capture these locked rows. Their internal
  structure is UNKNOWN.
- An assignment can be tied to an exam: the past-term course had a row
  whose expanded state showed a `View exam` link
  (`…/student/exam/info/id-<token>` — an exam **does** have its own URL,
  unlike an assignment detail) and an `Uncheck` button (the inverse of
  `Check off`, on an already-checked item).
- A later capture of that same past-term course's full list returned **all
  26 rows** (9 `Closed` + 17 `Completed`) once the recon row cap was
  raised, confirming the collapsed-row layout holds across the whole list,
  including attendance rows (`0%` weight) and one `(Ungraded)` row. The
  expanded row in that capture again had `#descriptionBlock` /
  `#AssignmentDescription` present but with **no body text reaching the
  recon descendant walk** — the description body is deeper than the walk's
  depth/node caps, so description text is still not captured.

Still UNKNOWN for the assignment list: what `Show Course Homework ID`
reveals (likely the stable per-assignment id — the toggle was located but
not activated in a capture), the description **body text** (needs a
targeted recon capture of `#AssignmentDescription`), the collapsed
structure of a `Check off` row and of locked `Opens <date>` rows, the
`*` / `§` superscript meanings, and whether a third instructor keeps this
layout.

## Course list / course switcher (VERIFIED / UNKNOWN)

Direct evidence: a later capture set of the top-level Course List page and,
separately, an in-course page whose course-selection menu was open. Source
of `smartee/course/discovery.py`.

- The course-selection menu is one component that appears in both places:
  a `<button>` whose `aria-label` starts with "Show course selection menu"
  (collapsed: "... No course selected", `aria-expanded="false"`; open:
  "... Current course: <label>", `aria-expanded="true"`). Its course `<a>`
  entries are in the DOM only while `aria-expanded="true"`.
- In the open menu, each enrolled course is a single `<a>` with the course
  label as visible text and a populated `href`. In the clean in-course
  capture these hrefs classified as `learning_suite` (first time that type
  appeared) with path shape
  `/<session>/student/cid-<opaque-id>/student/home/dashboard`. The
  `cid-<opaque-id>` segment is stable for the same course across captures
  and contexts; the leading `<session>` segment (e.g. `.MjTJ`, prior
  `.-ZL-`) is per-session and not durable identity.
- The course `<a>` carries no `id`, no `data-course-*`, no per-course
  `aria-*`; identity is only in the href path. `data-v-*` attributes are
  Vue build-scoped style markers (empty values, shared), not identity.
- Non-course menu links ("All Courses") resolve to paths without a
  `/student/cid-<id>/` segment (`/student/student/top`), so they are
  excluded structurally.
- The top-level Course List page also renders each course as an `<a>`
  (title) plus sibling "Go" `<a>`/`<button>`; that capture's `page.url` was
  a `cas.byu.edu` redirect URL, so only its path shapes are trustworthy.
  The clean in-course switcher capture is the source of truth.
- UNKNOWN: whether available/published courses can be distinguished from
  unavailable/unpublished ones. One course rendered differently on the
  Course List (bare `<a>`, empty label, no "Go") but the meaning of that
  variance was not established — no `disabled`/`aria-disabled`/"unavailable"
  marker was observed. Not implemented; stays UNKNOWN (Hard Rule 2).
- UNKNOWN: the interaction that expands the menu (no `aria-controls`, no
  handler captured); whether the menu lists all enrolled courses or only
  the current term's; the behavior on following a course entry (not
  navigated). A course delivered on an external platform had a switcher
  href straight to that host (no `cid-` in path) — such entries are not
  discovered by the current contract.

## Course-content patterns (VERIFIED / UNKNOWN)

- Content pages (`student/pages/...`) mix free-text headings with a large
  number of outbound links (25–49 per page in this sample) — consistent
  with instructor-authored content blocks containing many resource links
  per page rather than one link per page.
- UNKNOWN: quiz, grade, discussion, or exam page structure — none of
  these content types were visited in this capture set, so Hard Rule 1
  (never invent DOM/API behavior) applies fully to them; they stay
  UNKNOWN.

## Internal vs. external links (VERIFIED)

- Across all 634 captured links: 0 classified as `learning_suite`
  (see relative-URL explanation above), 498 `unknown` (no absolute
  href), 96 `external_web`, 25 `youtube`, 14 `box`, 1 `direct_document`.
- The single `direct_document` link was a `.pdf` hosted on a
  `*.byu.edu` subdomain — confirms at least one BYU-hosted subdomain
  serves direct downloadable files linked directly from course content,
  distinct from Box-hosted files.
- Every classified external link was cross-origin (`same_origin: false`
  in 100% of non-unknown, non-`learning_suite` cases) — no case of an
  external-looking host resolving to the same origin as the page.

## Observed Box / YouTube / external-platform patterns (VERIFIED)

- YouTube links appeared as both `youtu.be/...` short links and
  `www.youtube.com/watch?...` links across multiple courses/pages —
  confirms both link forms are in real use, not just one.
- Box links appeared under two distinct hostnames: `byu.box.com` and
  `byu.app.box.com` — both classify as `box` today; treat both as the
  same content source type.
- Other external `*.byu.edu` platforms linked from course content in this
  sample: a software-support site, a separate "learn anywhere" platform,
  a capstone-project site (also the source of the one `direct_document`
  PDF), a textbook/booklist site, and Zoom (`byu.zoom.us`).
- A few links pointed to fully external, non-BYU sites (a general news
  site, an industry trade-publication site, a retail site) — confirms
  instructor-authored content can link to arbitrary public external
  pages, not just a fixed set of platforms.
- UNKNOWN for all of the above: what happens when one of these links is
  actually followed (login wall vs. direct access, session reuse,
  redirect chain) — this capture set only recorded that the links exist
  on the page, never navigated to them. Open question #3 in
  `OPEN_QUESTIONS.md` is unchanged by this data.

## Redirects / external course platforms actually observed (VERIFIED)

- The only actual navigation/redirect observed was the initial,
  unauthenticated one: loading `learningsuite.byu.edu` redirected to a
  CAS login at `cas.byu.edu/cas/login`, whose query parameters (now
  stripped by the sanitizer fix in this change) showed the CAS flow is
  wired to an Okta SAML integration — the `entityId`/`service` params
  referenced an `okta.com` SAML service-provider callback, and the
  `RelayState` value itself further encoded an OAuth2
  `/authorize/redirect` step.
  - This confirms Learning Suite's unauthenticated entry point is
    CAS-fronted and CAS is federated to Okta via SAML.
  - Duo was **not** observed as a separate hostname/hop in this
    particular capture — this does not mean Duo isn't used (it may occur
    inside the CAS or Okta flow before the browser URL changes again, or
    the recon session's persistent profile already had a live/remembered
    session), only that this capture set provides no direct evidence of
    it. Open question #2 remains UNKNOWN beyond this.
- No other redirect was observed or attempted — all other 19 captures
  read `page.url` as a stable, already-loaded Learning Suite page.

## Remaining UNKNOWNs

- Duo's exact role/hop in the auth flow (open question #2).
- Session persistence behavior across separate tool runs/days (open
  question #2) — this dataset is one continuous run with one persistent
  profile, so nothing about session longevity was tested.
- Whether external platforms (Box, YouTube, Zoom, capstone/support sites)
  allow stable authorized session reuse or require separate logins (open
  question #3).
- Lecture transcript availability/format (open question #4) — no
  transcript link or reference appeared in this sample.
- Quiz, grade, and discussion page DOM structure — not visited.
- The exact user interaction that causes same-URL content swaps (tab
  click vs. lazy load vs. expand/collapse).
- The raw (pre-sanitization) href values behind the 498 `unknown`-typed
  links — only derived/sanitized fields are persisted, so relative paths
  can't be distinguished from `#`/`javascript:`/empty hrefs after the
  fact.
