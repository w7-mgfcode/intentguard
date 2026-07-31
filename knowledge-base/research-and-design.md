# Research and design

**Purpose:** Record the architecture alternatives, current platform findings,
critique, and final selection.

**Intended reader:** Maintainers reviewing why FPAT Lite has this shape.

**Consult this when:** Considering a restructure or adding platform-specific
features.

## Candidate architectures

Scores use 1–10, where 10 is best. “Low overengineering risk” is scored high
when the architecture is unlikely to grow ceremony.

| Criterion | Minimal shared files | Native command-oriented | Modular core + optional extensions |
|---|---:|---:|---:|
| Simplicity | 10 | 7 | 8 |
| Claude Code compatibility | 7 | 9 | 10 |
| Codex compatibility | 7 | 6 | 10 |
| Portability | 10 | 7 | 9 |
| Maintainability | 9 | 6 | 9 |
| Discoverability | 6 | 9 | 9 |
| Safety | 8 | 8 | 9 |
| Setup effort | 10 | 7 | 8 |
| Low overengineering risk | 10 | 5 | 8 |
| **Average** | **8.56** | **7.11** | **8.89** |

### Candidate A — minimal shared-file architecture

**Shape:** `AGENTS.md`, `CLAUDE.md`, shared commands, rules, and templates; no
native skills.

**Advantages**

- Smallest file and discovery surface.
- Maximum portability to unknown agents.
- Almost no platform churn.

**Disadvantages**

- Users must remember exact paths and prompts.
- Native skill menus and progressive disclosure are unused.
- Codex and Claude Code compatibility is conventional rather than ergonomic.

### Candidate B — command-oriented architecture

**Shape:** Copy six native commands into each platform plus shared background
documents.

**Advantages**

- Six commands are highly visible.
- Direct invocation is easy.

**Disadvantages**

- Twelve near-duplicate command definitions drift.
- Claude's `.claude/commands/` format is compatible but legacy.
- Codex custom prompts are deprecated, live in the user's Codex home, and are
  not a good repository distribution mechanism.
- Platform syntax leaks into model-independent rules.

### Candidate C — modular core plus optional extensions

**Shape:** Six shared command contracts, one thin skill router per platform,
three shared rule documents, short templates, on-demand knowledge, deterministic
scripts, and removable GitHub conveniences.

**Advantages**

- Uses native current skill discovery without duplicating workflow truth.
- Keeps startup context small.
- Provides a portable fallback.
- Advanced GitHub behavior can be removed without affecting the core.

**Disadvantages**

- Requires two small adapter files.
- Users must understand that `commands/` are contracts rather than native slash
  commands.
- Native platform behavior still needs periodic documentation review.

## Selection

Candidate C is selected, using Candidate A's shared-file discipline:

```text
one shared command source
+ one shared rule source
+ two thin native routers
+ optional, removable GitHub conveniences
```

## Verified platform findings

| Finding | Status | Design consequence | Primary source |
|---|---|---|---|
| Codex reads hierarchical `AGENTS.md` guidance | Officially documented | Root `AGENTS.md` is the shared instruction entry | [OpenAI](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| Codex repo skills use `.agents/skills/<name>/SKILL.md` | Officially documented | Add one Codex router skill | [OpenAI](https://learn.chatgpt.com/docs/build-skills) |
| Codex custom prompts are deprecated and user-home scoped | Officially documented | Do not create a repo `.codex/prompts` command copy | [OpenAI](https://learn.chatgpt.com/docs/custom-prompts) |
| Claude Code reads `CLAUDE.md`, not `AGENTS.md`, but supports imports | Officially documented | `CLAUDE.md` imports `AGENTS.md` | [Anthropic](https://code.claude.com/docs/en/memory) |
| Claude project skills use `.claude/skills/<name>/SKILL.md` | Officially documented | Add one Claude router skill | [Anthropic](https://code.claude.com/docs/en/skills) |
| Claude custom commands still work but skills are recommended | Officially documented | Omit `.claude/commands/` duplicate tree | [Anthropic](https://code.claude.com/docs/en/skills) |
| Claude permission rules enforce allow/ask/deny; instructions do not | Officially documented | Keep workflow policy honest; do not claim hard enforcement | [Anthropic](https://code.claude.com/docs/en/permissions) |
| GitHub CLI separates list/view commands from create/edit/merge actions | Officially documented | Maintain an effect-based mutation matrix | [GitHub CLI](https://cli.github.com/manual/gh) |
| `gh pr create --dry-run` may still push | Officially documented | Treat it as a remote-write action | [GitHub CLI](https://cli.github.com/manual/gh_pr_create) |

## Critique of the proposed design

### Duplication

**Attack:** Six `.claude/commands` files plus Claude and Codex skills would copy
the same instructions.

**Change:** Removed platform command copies. Both skills route to `commands/`.

### Unsupported symmetry

**Attack:** Presenting Claude slash commands and Codex prompts as equivalent
would overstate compatibility.

**Change:** Each platform uses its documented skill location and invocation.
The portable contract is explicitly a convention.

### Excessive rule fragmentation

**Attack:** Separate coding, Git, validation, safety, and approval documents
repeat the same boundaries.

**Change:** Reduced to core, safety/approval, and engineering/validation.

### Permission surprise

**Attack:** A checked-in platform settings file or `allowed-tools` frontmatter
could broaden permissions after repository trust.

**Change:** No permission grants are shipped. Hard-enforcement options are
explained, not activated.

### Ritual artifacts

**Attack:** Requiring request, brainstorm, plan, validation, and handoff files
for every change would recreate bureaucracy.

**Change:** Stable `.fpat/` paths are optional and created only when they add
continuity or review value.

### Hidden GitHub dependency

**Attack:** Prime would fail in a local repository without `gh`, authentication,
issues, Projects, or workflows.

**Change:** GitHub inspection is relevant-and-available, never a core
prerequisite.

### Fake enterprise automation

**Attack:** Porting label sync, dual tokens, rollup gates, and weekly audits
would dominate maintenance for small repositories.

**Change:** Removed them. The optional extension contains only templates and a
simple validation workflow.

### Handoff ownership

**Attack:** `.claude/handoffs/` makes continuity platform-specific.

**Change:** One `.fpat/handoff.md` works across agents.

### Long startup context

**Attack:** Importing the complete knowledge base into both instruction files
would reduce agent attention and create precedence conflicts.

**Change:** Startup files route; command, template, and knowledge content loads
on demand.

## Plan validation

The selected design:

- works with no GitHub account, Project, or paid service;
- has no runtime infrastructure;
- distinguishes local and remote mutation;
- has documented native entry points for Codex and Claude Code;
- gives other agents a portable fallback;
- includes a full health-endpoint example;
- can remove `extensions/` without breaking a link in the core workflow;
- contains no fixed task count or required hierarchy;
- has deterministic validation and packaging scripts.

## Reconsideration triggers

Revisit the architecture if either platform removes repository skills, changes
its documented discovery locations, or adopts one common repository skill path.
Do not restructure merely to mirror a new optional feature.

