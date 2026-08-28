# Session State

Transient "where we are right now" pointer. Not canonical: architecture is
in `ARCHITECTURE.md`, decisions in `DECISIONS.md`, open questions in
`OPEN_QUESTIONS.md`, recon findings in `docs/recon/OBSERVATIONS.md`.
Delete or rewrite entries here as work moves on.

## Current phase

Assignment Extractor — evidence phase.

## Immediate next action

Run real assignment reconnaissance with `scripts/recon_learning_suite.py`
against one real Learning Suite course. Capture only:

1. Assignment list, nothing expanded.
2. One expanded `Check off`-style assignment.
3. One expanded `Submit`-style assignment, if available.

Do not click `Check off` or `Submit` (Hard Rule 4). Then decide from
VERIFIED evidence only whether it is enough to build the smallest
deterministic Assignment Extractor; if not, request exactly one more
observation.

## Operational state

Branch `feat/assignment-extractor` is even with `main` (no commits yet).
