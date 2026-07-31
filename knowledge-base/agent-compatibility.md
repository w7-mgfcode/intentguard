# Agent compatibility

**Purpose:** Separate officially discovered behavior, shared conventions, and
portable fallbacks.

**Intended reader:** Maintainers installing FPAT Lite for Codex, Claude Code, or
another coding agent.

**Consult this when:** Editing agent-specific files or troubleshooting
discovery.

## Compatibility matrix

| Capability | Codex | Claude Code | FPAT Lite choice |
|---|---|---|---|
| Repository instructions | `AGENTS.md`; hierarchical scope | `CLAUDE.md`; hierarchical scope | Shared rules in `AGENTS.md`; `CLAUDE.md` imports it |
| Repository skill | `.agents/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` | One thin router in each native location |
| Explicit invocation | `$fpat-lite ...` or skill selector | `/fpat-lite ...` | Same mode and arguments |
| Reusable command files | Codex custom prompts are deprecated and user-home scoped | `.claude/commands/` works but is legacy | `commands/` are portable contracts, not native commands |
| Permission control | Sandbox, approvals, configuration, experimental exec rules | Permission modes, allow/ask/deny rules, hooks | No silent grants; document approval boundary |
| Shared detailed knowledge | Skill references and ordinary repository files | Skill references and ordinary repository files | Shared `commands/`, `rules/`, `templates/`, `knowledge-base/` |
| Other agents | No guaranteed native discovery | No guaranteed native discovery | Read `AGENTS.md` then a named command contract |

## Codex behavior used

Current Codex guidance documents that:

- Codex builds an `AGENTS.md` instruction chain from global guidance and the
  project root down to the working directory; closer files appear later and
  take precedence.
- Repository skills are discovered under `.agents/skills` from the working
  directory through the repository root.
- Skills require a `SKILL.md` with `name` and `description`, and support
  progressive disclosure.
- Custom prompts are deprecated in favor of skills and live in the user's Codex
  home rather than the repository.

Sources:

- [Codex `AGENTS.md` guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [OpenAI skill authoring](https://learn.chatgpt.com/docs/build-skills)
- [Codex custom prompts](https://learn.chatgpt.com/docs/custom-prompts)

## Claude Code behavior used

Current Claude Code documentation states that:

- Project instructions may live in `./CLAUDE.md` or `./.claude/CLAUDE.md`.
- Claude Code reads `CLAUDE.md`, not `AGENTS.md`, but `CLAUDE.md` can import
  `AGENTS.md` with `@AGENTS.md`.
- Project skills live at `.claude/skills/<skill-name>/SKILL.md` and can be
  invoked as `/skill-name`.
- `.claude/commands/` continues to work, but skills are the recommended current
  format.
- Instructions shape behavior; permission rules and hooks provide enforcement.

Sources:

- [Claude Code project memory](https://code.claude.com/docs/en/memory)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)
- [Claude configuration directory](https://code.claude.com/docs/en/claude-directory)

## Instruction precedence differences

Both products combine broader and narrower guidance, but their details are not
identical:

- Codex checks `AGENTS.override.md`, then `AGENTS.md`, at each applicable
  directory and uses one file per directory.
- Claude Code loads `CLAUDE.md` and `CLAUDE.local.md`; project instructions
  appear after user instructions, and subdirectory files can load on demand.
- Claude imports are native Claude behavior. Codex is not told to interpret the
  `@AGENTS.md` line; it reads `AGENTS.md` directly.

Do not describe either product's exact precedence as a universal Agent Skills
standard.

## Permission guidance

FPAT Lite deliberately omits checked-in `allowed-tools`, auto-approval rules,
and broad platform settings. Such files can alter the user's security posture
and are environment-specific.

Teams that need hard enforcement should configure the platform directly:

- Codex: sandbox, approval policy, trusted project config, and organization
  policy.
- Claude Code: permission modes, `allow`/`ask`/`deny` rules, or hooks.
- GitHub: least-privilege tokens, branch protection, required checks, and
  reviewer policy.

Keep the Markdown approval rule even when enforcement exists; it explains the
intent and improves handoffs.

## Portable fallback

When native skill discovery is unavailable, use:

```text
Read AGENTS.md, rules/core-rules.md, and
rules/safety-and-approval.md. Then follow commands/<mode>.md for this task.
```

This fallback is a documented convention, not a claimed native feature.

