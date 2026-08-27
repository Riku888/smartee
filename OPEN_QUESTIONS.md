# Open Questions

These remain `UNKNOWN` until tested against the actual environment. Source of truth is `ARCHITECTURE.md` §40 — update both together. Do not prematurely "resolve" these with AI intuition.

1. Exact Learning Suite DOM/page patterns for each relevant content type.
   Partially informed by real captures for home/dashboard, assignments,
   a generic content page, and syllabus — see `docs/recon/OBSERVATIONS.md`.
   Quiz, grade, and discussion page structure remain fully UNKNOWN
   (not yet visited), so this item stays open.
2. Session persistence behavior under BYU authentication and Duo.
3. Whether specific external course systems allow stable authorized browser-session reuse.
4. Availability and format of lecture transcripts.
5. Best parsing strategy for each document type encountered in real courses.
6. Whether Obsidian CLI, direct Markdown, or Headless is the best v1 write path for the user's real devices.
7. Actual context-compiler thresholds that improve quality on this workload.
8. Actual model routing that minimizes cost without reducing note/verification quality.
9. Priority-scoring formula that matches the student's real preferences.
10. Mastery signals that predict genuine understanding rather than superficial completion.

Move an item out of this file (into `DECISIONS.md`) only once it has actually been verified against the real environment — not reasoned about.
