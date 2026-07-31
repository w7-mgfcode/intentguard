# FPAT Lite command contracts

**Purpose:** Route a task to one proportionate workflow.

**Intended reader:** Developers, coding agents, and maintainers.

**Consult this when:** Choosing what FPAT Lite should do next.

| Command | Choose it when | Default mutation level |
|---|---|---|
| [prime](prime.md) | Context is new, stale, or uncertain | Read-only |
| [brainstorm](brainstorm.md) | The solution direction is unclear | Read-only |
| [plan](plan.md) | A direction must become verifiable work | Read-only |
| [implement](implement.md) | The user requested a local change | Local files |
| [validate](validate.md) | Claims need executed evidence | Read-only or temporary local artifacts |
| [handoff](handoff.md) | Work will pause or context must transfer | Local checkpoint |

Use one primary command at a time. A command may recommend the next one, but it
must not silently cross into a higher-mutation mode.

Native invocation:

```text
Codex:       $fpat-lite <mode> [task]
Claude Code: /fpat-lite <mode> [task]
Portable:    Follow commands/<mode>.md for [task]
```

Shared rules:

- [Core rules](../rules/core-rules.md)
- [Safety and approval](../rules/safety-and-approval.md)
- [Engineering and validation](../rules/engineering-and-validation.md)

