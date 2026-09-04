# Decisions

Accepted architecture decisions for the current baseline. Source of truth is `ARCHITECTURE.md` §39 — update both together.

| ID | Decision |
|---|---|
| D-001 | The product is a Learning OS, not an assignment submission bot. |
| D-002 | Automatic graded submission is not implemented. |
| D-003 | Obsidian is the v1 human-facing knowledge layer. |
| D-004 | PostgreSQL is the structured operational store. |
| D-005 | pgvector is the initial semantic retrieval layer. |
| D-006 | Raw source documents are preserved separately from generated notes. |
| D-007 | Material acquisition includes a first-class HUMAN_REQUIRED fallback. |
| D-008 | The Teacher performs pedagogical reconstruction, not simple summarization. |
| D-009 | Source facts and AI enrichment are explicitly separated. |
| D-010 | A small specialist-agent architecture is preferred over a mega-agent or agent swarm. |
| D-011 | Verification is independent of worker self-report. |
| D-012 | Context Compiler principles are adopted; ContextForge is optional/reference, not a hard dependency. |
| D-013 | WSL2 Ubuntu is the primary development environment. |
| D-014 | AWS is initially a deployment target, not the primary development machine. |
| D-015 | BYU authentication/session artifacts remain in the Local Trust Zone by default. |
| D-016 | Production target is Local Collector + Cloud Processing hybrid. |
| D-017 | MCP is used at external system boundaries, not for every internal function. |
| D-018 | Autonomy increases progressively only after measured reliability. |
| D-019 | Every unattended loop requires verifier, budget, stop conditions, persistent state, and human escalation. |
| D-020 | GitHub issues + acceptance criteria + fixtures are the basis for AI-assisted development. |
| D-021 | Claude Code project memory stays concise; full design remains in canonical docs. |
| D-022 | Model routing is eval-driven and provider-configurable. |
| D-023 | The read-only Collector may click course entries in the course-switcher menu (not only the toggle); a bare URL `goto` does not switch the assignments view. Still no submission/row/detail control is ever clicked. |

New decisions should be appended here with the next sequential ID as they're made.
