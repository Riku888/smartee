---
name: pr-description
description: Generate a pull request description for this repo's required template (Goal, What changed, Acceptance criteria, Tests run, Known limitations/UNKNOWNs, Security impact). Use when the user asks to write, draft, or update a PR description, or to open a PR.
---

Generate a PR description for the current branch's changes against `main`, using exactly this template (omit "Security impact" only if truly not applicable, and say so explicitly rather than deleting the section silently):

```markdown
## Goal
<why this change exists, one or two sentences>

## What changed
<concrete summary of the diff, not a restatement of file names>

## Acceptance criteria
<what must be true for this to be considered done — bullet list>

## Tests run
<only tests you actually executed and their result; never claim a test passed unless it was run in this session>

## Known limitations / UNKNOWNs
<anything ASSUMED or UNKNOWN per CLAUDE.md's evidence-state discipline; "None" if genuinely none>

## Security impact
<credentials, secrets, auth boundaries, or untrusted-data handling touched by this change; "None" if genuinely none>
```

Before writing it:
1. Run `git log main..HEAD --oneline` and `git diff main...HEAD` (or the equivalent against the PR's target branch) to see the actual changes — do not infer content from memory of the conversation alone.
2. Only list tests under "Tests run" that you actually executed in this session; if none were run, say so plainly rather than omitting the section.
3. Cross-check "Known limitations / UNKNOWNs" against `OPEN_QUESTIONS.md` if the change touches an area already flagged there.

If the user wants it posted as an actual PR (not just drafted), use `gh pr create --body "..."` with this content, following the branch-naming convention in `CLAUDE.md`.
