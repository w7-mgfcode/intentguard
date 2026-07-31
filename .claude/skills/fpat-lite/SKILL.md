---
name: fpat-lite
description: Apply FPAT Lite's prime, brainstorm, plan, implement, validate, or handoff workflow to repository work. Use when the user names FPAT Lite, asks for a governed coding workflow, or requests one of these six modes.
argument-hint: "<prime|brainstorm|plan|implement|validate|handoff> [task]"
---

# FPAT Lite router for Claude Code

Invocation arguments:

```text
$ARGUMENTS
```

Interpret them as `<mode> [task or arguments]`.

1. Read `CLAUDE.md`, which imports the shared `AGENTS.md`.
2. Read `rules/core-rules.md` and `rules/safety-and-approval.md`.
3. Read only `commands/<mode>.md`.
4. Follow that command's inputs, procedure, mutation boundary, output contract,
   stop conditions, and failure handling.
5. Load templates or knowledge-base files only when the command points to them.
6. If no valid mode is supplied, recommend the smallest suitable mode. Ask only
   when choosing incorrectly would change scope, authority, or mutation risk.

This skill deliberately declares no `allowed-tools`; repository skills must not
silently pre-approve local or remote mutations.

