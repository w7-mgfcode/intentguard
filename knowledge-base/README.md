# FPAT Lite knowledge base

**Purpose:** Explain the design without inflating startup instructions.

**Intended reader:** Developers, maintainers, and agents resolving a specific
workflow question.

**Consult this when:** A command or rule links here, or when adapting the toolkit.

## Reading routes

| Question | Read |
|---|---|
| What is the system boundary? | [architecture.md](architecture.md) |
| Which command should run next? | [workflow.md](workflow.md) |
| How do Codex and Claude Code differ? | [agent-compatibility.md](agent-compatibility.md) |
| What did the nine original diagrams specify? | [original-fpat-analysis.md](original-fpat-analysis.md) |
| Why was this architecture selected? | [research-and-design.md](research-and-design.md) |
| What does a term mean? | [glossary.md](glossary.md) |
| Why is discovery or validation failing? | [troubleshooting.md](troubleshooting.md) |
| What is the durable scope decision? | [decisions/0001-fpat-lite-scope.md](decisions/0001-fpat-lite-scope.md) |

## What FPAT Lite removed

The core does not require initiative, umbrella, epic, or fixed five-sub-issue
hierarchy; GitHub Project field synchronization; rollup enforcement; weekly
board audits; personal access tokens; scheduled workflows; or multi-agent
orchestration.

Those mechanisms can be valuable in a large governed delivery program, but they
are not prerequisites for safe, evidence-backed work in an ordinary repository.

## Maintenance rule

Keep operational truth in:

- `commands/` for procedures and output contracts;
- `rules/` for invariants;
- `templates/` for artifact shape;
- platform files only for discovery and invocation.

Do not copy a command into this knowledge base. Explain the reason and link to
the canonical contract.

