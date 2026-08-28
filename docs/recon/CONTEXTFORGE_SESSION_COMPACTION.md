# Smartee — ContextForge Session Compaction Guide

## Purpose

Use ContextForge as a **session compactor** for long Claude Code development sessions.

Do **not** place ContextForge in front of Claude Code as a permanent proxy. The current ContextForge v0.1 proxy is not fully compatible with Claude Code's request/tool protocol in our testing.

The intended model is:

```text
Smartee repo = long-term source of truth
Claude Code session = working memory
ContextForge = occasional session compactor / handoff generator
```

## Environment

### Smartee

- Repo: `~/projects/smartee`
- Python: 3.12
- Dependency/tooling manager: `uv`
- Claude Code is used for development.

### ContextForge

- Repo: `~/context-forge`
- Installed separately from Smartee.
- Virtual environment: `~/context-forge/.venv`
- CLI:

```bash
~/context-forge/.venv/bin/contextforge
```

Smartee should continue using `uv`. ContextForge remains isolated in its own virtual environment.

## Files added to Smartee

```text
scripts/context/
├── claude_to_contextforge.py
└── compact_session.py

.local/context/
├── traces/
└── compiled/
```

`.local/` is gitignored and must remain local.

### `claude_to_contextforge.py`

Converts a Claude Code `.jsonl` transcript into a ContextForge Trace.

Keeps:

- user messages
- visible assistant messages
- useful tool results

Drops:

- Claude private thinking
- redacted thinking
- raw `tool_use` blocks
- session/permission metadata
- Claude-generated `## Context Usage` diagnostics

### `compact_session.py`

Runs the complete manual compaction pipeline:

```text
Claude Code transcript
    ↓
claude_to_contextforge.py
    ↓
ContextForge Trace
    ↓
contextforge score
    ↓
contextforge compile
    ↓
.local/context/compiled/latest.json
```

If the transcript contains no durable development conversation, it exits safely without invoking ContextForge.

## Normal development workflow

Develop Smartee normally in Claude Code.

Do not run ContextForge after every message.

Use the repository documents as canonical truth, especially:

1. `CLAUDE.md`
2. `SECURITY.md`
3. `DECISIONS.md`
4. `OPEN_QUESTIONS.md`
5. `ARCHITECTURE.md`
6. `docs/recon/OBSERVATIONS.md`

Prefer repository state over old conversation history.

## When to compact

Run compaction when one or more of these are true:

- the Claude session has become very long
- Claude starts mixing old and current decisions
- a major implementation phase has finished
- a large amount of terminal/tool output has accumulated
- Claude Code is approaching auto-compaction
- you want to start a clean Claude session without losing important context

There is no need to compact a small or fresh session.

## Manual compaction

From the Smartee repo:

```bash
cd ~/projects/smartee
```

Find the newest Smartee Claude transcript:

```bash
LATEST=$(find ~/.claude/projects/-home-admin-user-projects-smartee   -type f -name '*.jsonl'   -printf '%T@ %p\n' 2>/dev/null   | sort -nr   | head -1   | cut -d' ' -f2-)
```

Confirm it:

```bash
echo "$LATEST"
```

Run the compactor:

```bash
uv run python scripts/context/compact_session.py "$LATEST"
```

Default token budget:

```text
30,000 tokens
```

To use another budget:

```bash
uv run python scripts/context/compact_session.py   "$LATEST"   --budget 20000
```

## Outputs

Raw converted ContextForge Trace:

```text
.local/context/traces/latest.json
```

Compiled output:

```text
.local/context/compiled/latest.json
```

Both remain local and should not be committed.

## Expected behavior for a new session

A new Claude session can contain only generated metadata such as `## Context Usage`.

In that case the converter may report:

```text
Items: 0

No durable conversation items found. Skipping ContextForge.
```

This is expected and means there is nothing useful to compact yet.

## ContextForge testing already completed

ContextForge was installed and tested successfully.

Bundled demo:

```text
251,933 tokens → 1,902 tokens
rot risk 44 → 3
```

OpenHands coding-agent demo:

```text
171,173 tokens → 19,655 tokens
88.5% token reduction
rot risk 33 → 15
critical constraint preserved
```

These are demonstration workloads and do not guarantee the same reduction on Smartee sessions.

## Claude Code proxy experiment

We tested:

```text
Claude Code
    ↓
ContextForge proxy
    ↓
Anthropic
```

The ContextForge proxy itself worked with direct Anthropic-style requests, but it was not fully compatible with Claude Code's complete request/protocol behavior.

Therefore:

```text
DO NOT use ContextForge as the permanent Claude Code proxy.
```

Use it as an offline/session compactor instead.

## Security

Never commit:

- Claude raw transcripts
- raw tool results that may contain sensitive information
- browser/session state
- cookies
- credentials
- `.env`
- authenticated reconnaissance data
- compiled context containing private course data

Keep generated traces and compiled output under `.local/context/`.

## Planned automation

The manual workflow should be validated on a real, long Smartee Claude session first.

After that, the intended automation is:

```text
Claude Code session becomes large
        ↓
PreCompact hook
        ↓
compact_session.py
        ↓
ContextForge
        ↓
compiled handoff
        ↓
new/compacted Claude context
```

Do not enable the hook until the manual end-to-end flow has been verified on real development data.

## Current status

Completed:

- ContextForge installed separately
- ContextForge CLI tested
- large-context demos tested
- Claude transcript location identified
- Claude JSONL → ContextForge Trace converter created
- generated Claude metadata filtering added
- manual compaction wrapper created
- empty-session behavior verified

Remaining:

- generate a real long Smartee Claude development transcript
- run the manual compactor against it
- inspect what ContextForge preserves/drops
- verify current decisions and evidence survive compaction
- only then automate with Claude Code hooks
