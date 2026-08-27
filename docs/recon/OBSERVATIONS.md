# Learning Suite Recon Observations

Source: 20 read-only DOM snapshots captured with `scripts/recon_learning_suite.py`
across 4 distinct courses, one authentication flow, and repeat visits to the
same URLs. Raw capture JSON stays local (`.local/recon/output/`, gitignored)
and is never quoted here — this file contains only sanitized structural
findings. No course names, course codes, headings text, file names, or
account/profile identifiers from the captures are reproduced below, since
several captured headings, button labels, and a linked filename were
personally identifying or course-private (Hard Rule 6 / `SECURITY.md`).

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
