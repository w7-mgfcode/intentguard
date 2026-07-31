---
name: fpat-lite
description: Apply FPAT Lite's prime, brainstorm, plan, implement, validate, or handoff workflow to repository work. Use when the user names FPAT Lite, asks for a governed coding workflow, or requests one of these six modes.
---

# FPAT Lite router for Codex

Interpret the text following `$fpat-lite` as:

```text
<mode> [task or arguments]
```

Allowed modes are `prime`, `brainstorm`, `plan`, `implement`, `validate`, and
`handoff`.

1. Read the repository `AGENTS.md`.
2. Read `rules/core-rules.md` and `rules/safety-and-approval.md`.
3. Read only `commands/<mode>.md`.
4. Follow that command's inputs, procedure, mutation boundary, output contract,
   stop conditions, and failure handling.
5. Load templates or knowledge-base files only when the command points to them.
6. If no valid mode is supplied, recommend the smallest suitable mode. Ask only
   when choosing incorrectly would change scope, authority, or mutation risk.

Do not treat shared Markdown command contracts as Codex slash commands. This
skill is the native Codex entry point.

