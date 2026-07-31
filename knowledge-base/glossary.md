# Glossary

**Purpose:** Define FPAT Lite terms consistently.

**Intended reader:** New users and maintainers.

**Consult this when:** A workflow term is ambiguous.

- **Acceptance criterion:** Observable condition that determines whether the
  requested outcome is satisfied.
- **Agent adapter:** Thin platform-specific file that discovers and routes to
  shared FPAT Lite contracts.
- **Baseline:** Verified snapshot of repository instructions, Git state, stack,
  active work, and relevant remote context.
- **Command contract:** Model-independent Markdown procedure for one operational
  mode; it is not automatically a native slash command.
- **Evidence:** A file, source, diff, executed command, exit status, or observed
  behavior supporting a claim.
- **External mutation:** A write to GitHub or another remote system, including
  pushes, issue changes, PR actions, workflow dispatches, releases, or messages.
- **Handoff:** A verified local checkpoint that lets another session resume.
- **Local mutation:** A change to files or state in the local workspace.
- **Material uncertainty:** Unknown fact that can change scope, architecture,
  safety, cost, compatibility, or acceptance.
- **Prime:** Read-only session entry and context capture.
- **Progressive disclosure:** Loading detailed skill instructions only when the
  skill is selected rather than placing everything in startup context.
- **Remote approval:** Current, target-specific authorization for an external
  write.
- **Source of truth:** The authoritative source for one question, such as live
  code for current behavior or current test output for a pass claim.
- **Working artifact:** Optional file under `.fpat/` that preserves a request,
  decision, plan, validation report, or handoff.

