# Decision 0001: Keep FPAT Lite as a shared modular core

- **Status:** Accepted
- **Date:** 2026-07-31

## Context

The original FPAT design combines safe agent behavior with a GitHub-specific
issue hierarchy, Project v2 synchronization, rollup enforcement, scheduled
audits, and fixed five-subtask decomposition. The target user is a solo
developer or small team that needs the governance benefits without operating a
delivery platform.

Current Codex and Claude Code both support repository skills, but they discover
them from different native locations. Their instruction files and exact
precedence rules also differ.

## Assumptions

- Most repositories already have their own build, test, Git, and CI tools.
- Remote GitHub automation is not necessary for the core safety loop.
- A small amount of platform-specific routing is more maintainable than copied
  workflows.

## Options considered

| Option | Advantages | Disadvantages | Evidence |
|---|---|---|---|
| Shared files only | Simplest and portable | Weak native discoverability | Platform docs |
| Copied native commands | Visible invocation | Duplication and deprecated/legacy formats | Platform docs |
| Shared core plus two skill routers | Native discovery without workflow duplication | Two adapters to maintain | Platform docs and critique |

## Decision

Use six shared command contracts, three shared rule documents, optional
templates and knowledge, and one thin skill router in each platform's documented
repository skill location. Keep GitHub governance removable and nonessential.

## Consequences

- Positive: one operational source of truth works across agents.
- Positive: startup context stays small.
- Positive: no fixed hierarchy, board, token, or service is required.
- Negative: maintainers must periodically verify two native discovery paths.
- Neutral: `commands/` are portable contracts rather than direct slash commands.

## Reconsideration trigger

Revisit if the platforms adopt a common repository skill location or either
platform removes the discovery behavior on which an adapter depends.

## Unresolved questions

- No scope-blocking question remains. Hard permission policy stays
  environment-specific by design.

