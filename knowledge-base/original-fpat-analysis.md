# Original FPAT reconstruction

**Purpose:** Reconstruct the attached nine-card FPAT workflow before
simplification and make every retained or removed mechanism traceable.

**Intended reader:** Maintainers evaluating whether FPAT Lite preserved the
important governance.

**Consult this when:** Comparing FPAT Lite with the original diagrams or
considering a governance extension.

## Evidence boundary

The observations below come from the supplied session-entry, decomposition,
continuation-planning, execution-pipeline, implementation, board-automation,
gate-enforcement, audit-sweep, and handoff diagrams plus the supplied FPAT
framework report and visual HTML/CSS.

The diagrams define a concrete GitHub-centric operating model. The conclusion
that some mechanisms are excessive for a solo developer is a design judgment,
not an assertion that those mechanisms are incorrect.

## System purpose

Original FPAT—Flow-Pack Agent-Team—is a governed delivery system for coding
agents:

```text
read-only entry
→ scored planning
→ fixed issue decomposition
→ approval-gated GitHub writes
→ branch / PR / checks / merge
→ board synchronization
→ parent-close enforcement
→ scheduled invariant audit
→ resumable handoff
→ evidence-gated release
```

Its primary optimization is control and traceability across a GitHub issue tree,
not minimal setup.

## Actors

| Actor | Responsibility |
|---|---|
| User / operator | Supplies goal, invokes commands, approves mutation packages |
| Coding agent | Reads context, plans, edits, validates, and reports evidence |
| Critic role | Attacks scope, weak evidence, blockers, and overengineering |
| Research role | Checks known issues, practices, and dependencies |
| GitHub repository | Holds code, branches, issues, PRs, workflows, and history |
| GitHub Projects v2 | Holds Type, Phase, Area, Status, and Score fields |
| CI and review services | Validate a PR before merge |
| Scheduled audit workflow | Checks board invariants without mutation |
| Next session / agent | Resumes from the handoff checkpoint |

Critic and research are workflow roles; the diagrams do not require that they
be separate autonomous agents.

## Workflow-by-workflow reconstruction

### 1. Session entry — `/fpat-prime`

| Dimension | Observed behavior |
|---|---|
| Purpose | Capture a baseline before every FPAT session |
| Trigger | Operator invokes `/fpat-prime` |
| Local sources | `AGENTS.md`, `CLAUDE.md`, `board-spec.md`, `rules/README.md` |
| Remote reads | `gh repo view`, issue list, Project list, workflow list |
| Decision | Are FPAT assets missing or broken? |
| Failure path | Flag gaps in the report |
| Success path | Produce a concise baseline report |
| Artifact | Cited, read-only report under 300 words |
| Gate | No mutation beyond the entry gate until baseline passes |

Useful invariant: context and live state precede action.

### 2. Decomposition — phased issue tree

| Dimension | Observed behavior |
|---|---|
| Purpose | Turn one initiative into a GitHub-native execution hierarchy |
| Hierarchy | Initiative → umbrella → epics → five sub-issues each |
| Foundation | One blocking foundation epic closes first |
| Parallel phase | Three example epics run concurrently after foundation |
| Release | One release epic stays locked until all parallel epics close |
| Executable unit | Only a sub-issue may be implemented directly |
| Closure | PR closes a sub-issue; parent closes after all children close |
| Sub-issue fields | Conventional-commit title, type, area, parent, acceptance criteria |

Useful invariant: executable work is small and independently verifiable.
Excessive default: every epic has exactly five children and every goal needs
umbrella/foundation/parallel/release structure.

### 3. Continuation planning — V1 to V2

| Dimension | Observed behavior |
|---|---|
| Input | Goal or arguments |
| Baseline | Repository, docs, rules, open issues, and live state |
| Freeze | Timestamp makes the captured baseline immutable for the plan |
| Draft | Five to ten deliberately unscored V1 candidates |
| Critique | Weak assumptions, scope creep, and missing evidence |
| Research | Three passes: known issues, best practices, dependencies |
| Score | Value, risk, readiness, complexity, and evidence; total out of 50 |
| Bands | Ship at 40+, negotiate at 36–39, defer below 36 |
| Artifact | V2 plan with ship / negotiate / defer lists |
| Gate | No GitHub writes until user approves V2 |

Useful invariants: critique before commitment, research material uncertainty,
and separate planning from mutation. Simplification opportunity: fixed scoring
dimensions and thresholds are disproportionate for many small changes.

### 4. Execution pipeline — issue to five subtasks

| Dimension | Observed behavior |
|---|---|
| Input | Issue number or URL |
| Resolution | Resolve canonical `owner/repo#N` |
| Context | Load title, body, labels, state, parent, children, PRs, comments |
| Framing | Brief, source of truth, scope, risks, blockers |
| Score | Value, risk, readiness, dependency load, validation ease, rollback safety, evidence |
| Critique | Scope creep, weak evidence, blockers, overengineering |
| Decomposition | Exactly five subtasks |
| Task contract | Title, purpose, scope, out-of-scope, dependencies, acceptance |
| Approval | Present a read-only package and revise until approved |
| Mutation | Create five GitHub sub-issues after approval |

Useful invariant: present a complete mutation package before a remote write.
Excessive default: exactly five tasks regardless of natural work shape.

### 5. Implementation — branch to PR to merge

| Dimension | Observed behavior |
|---|---|
| Input | Approved sub-issue |
| Branch | One named branch per sub-issue |
| Edit loop | Implement → lint/build → fix and rerun |
| Commit | Conventional commit with parent epic reference |
| PR | Labels, milestone, assignee/reviewer, mandatory `Closes #N` |
| Checks | FPAT Validate, CodeRabbit, Sourcery, Socket, and Vercel examples |
| Gate | All checks must be green |
| Merge | Squash merge to main |
| Cascade | Sub-issue closes, epic rollup advances, board Status becomes Done |

Useful invariants: one coherent delivery unit, real validation, intentional
closure link, and bottom-up progress. Optional details: named third-party checks,
mandatory labels/milestones, and fixed merge strategy.

### 6. Board automation — labels to fields

| Dimension | Observed behavior |
|---|---|
| Triggers | Opened, labeled, unlabeled, reopened, manual dispatch |
| Workflow | `fpat-project-sync.yml` |
| Inputs | `type:*`, `phase:*`, and `area:*` labels |
| Outputs | Project Type, Phase, and Area fields |
| Tokens | Built-in token reads; separate project token writes GraphQL |
| Resolution | Field and option names resolved at runtime; no hardcoded IDs |
| Safety | One-directional, idempotent, no duplicates |
| Protected | Status and Score are never written |
| Missing label | Existing field remains untouched rather than being cleared |

Useful only when a team relies on GitHub Projects v2 as an operational board.
It introduces token, GraphQL, field-schema, and maintenance overhead.

### 7. Gate enforcement — rollup gate

| Dimension | Observed behavior |
|---|---|
| Trigger | Epic or umbrella issue closes |
| Workflow | `fpat-rollup-gate.yml` |
| Query | Native sub-issues and paginated summary |
| Decision | Does the parent have any open children? |
| Premature path | Reopen parent and comment the blocker list |
| Valid path | Parent remains closed |
| Cascade | One level per event; repeated close events move bottom-up |
| Scope | Writes issue state, never board fields |

Useful invariant: a parent cannot represent completion while descendants remain
open. Optional mechanism: automatic reopen/comment workflow.

### 8. Audit sweep — blocked sweep

| Dimension | Observed behavior |
|---|---|
| Trigger | Monday 07:17 UTC or manual dispatch |
| Workflow | `fpat-blocked-sweep.yml` |
| Access | Project token reads only |
| Inputs | Board items plus Type, Phase, Status, and Score |
| Invariant 1 | Parallel work must not progress before foundation closes |
| Invariant 2 | Epic must not leave Backlog with Score below 40 |
| Invariant 3 | Surface blocked label or Blocked status items |
| Resilience | Missing or renamed field warns but does not crash |
| Artifact | Workflow job summary |
| Gate | Stop read-only; no issue edits or board writes |

Useful for a large persistent board. Disproportionate as a mandatory weekly
workflow for a small repository.

### 9. Handoff — session checkpoint

| Dimension | Observed behavior |
|---|---|
| Trigger | Session pause or stage completion |
| Command | `/fpat-handoff <stage>` |
| State | Exactly one of dry-run, applying, or blocked |
| Captures | Completed work and evidence, GitHub surface, decisions, files, validation, next action, pending mutations |
| Artifact | `.claude/handoffs/fpat-<slug>.md` |
| Consumer | Next session |
| Decision | Does user approve pending mutations? |
| Approved path | Apply writes from pending list |
| Not approved | Wait; checkpoint remains source of truth |

Useful invariant: continuity is explicit and evidence-backed. Simplification:
one stable `.fpat/handoff.md` works across agents and avoids platform ownership.

### 10. Release layer from the report

The supplied framework report adds a release condition: dogfood the whole
system and close the umbrella only after evidence exists. This is consistent
with the rollup and validation gates, although the nine cards emphasize the
preceding mechanisms rather than a separate release card.

## Decision points

1. Are baseline assets missing or conflicting?
2. Which plan candidates survive critique and research?
3. Which score band receives each candidate?
4. Does decomposition need revision before approval?
5. Did local lint/build gates pass?
6. Did all PR checks pass?
7. Does a parent have open children?
8. Do board items violate phase, score, or blocked invariants?
9. Is an expected board field missing or renamed?
10. Is the session planning, applying, blocked, or ready?
11. Has the user approved each pending external mutation?
12. Does release evidence justify top-level closure?

## Mutation inventory

| Mutation | Initiator | Original gate |
|---|---|---|
| Create sub-issues | Execution pipeline | User approves package |
| Create branch and edit files | Implementation | Approved sub-issue |
| Commit and create PR | Implementation | Local checks pass |
| Push / merge | Implementation | PR checks green |
| Close sub-issue | Merge plus `Closes #N` | PR merged |
| Update Project fields | Project sync automation | Matching labels and token |
| Reopen parent and comment | Rollup gate | Parent closes with open children |
| Apply pending board writes | Handoff continuation | User approves pending list |
| Close release / umbrella | Release layer | Dogfood evidence and descendants closed |

The audit sweep and prime workflow are deliberately read-only.

## Validation gates

- Baseline passes before any write.
- V2 plan is approved before GitHub planning writes.
- Task package is approved before sub-issues are created.
- Lint and build pass before commit.
- All PR checks pass before merge.
- All children close before a parent remains closed.
- Board invariants are audited and reported.
- Release requires end-to-end evidence.

## Sources of truth and artifacts

| Stage | Source of truth | Artifact |
|---|---|---|
| Entry | Local instructions plus live GitHub state | Baseline report |
| Planning | Frozen baseline and research | V2 plan |
| Decomposition | Approved issue graph | Five-subtask package and sub-issues |
| Implementation | Approved sub-issue and repository | Branch, commit, PR, checks |
| Board | Labels and Project schema | Field values |
| Enforcement | Native child issue state | Reopen comment or valid close |
| Audit | Board item snapshot | Job summary |
| Continuity | Verified live session state | Handoff checkpoint |
| Release | Dogfood evidence and closed descendants | Final closure |

## Dependencies between stages

```text
Foundation closes
→ parallel epics unlock
→ all parallel epics close
→ release epic unlocks
→ all release children close
→ release epic closes
→ umbrella can close
```

At the work-unit level:

```text
approved plan
→ approved sub-issue
→ branch
→ local checks
→ PR
→ external checks
→ merge
→ child closes
→ parent progress rolls up
```

## Simplification classification

### KEEP

- Read-only baseline before action.
- Instruction and repository inspection before editing.
- Known facts separated from assumptions.
- Brainstorming that includes a simple option.
- Focused research of material uncertainty.
- Proportionate plan with scope, non-goals, acceptance criteria, risks, and
  validation.
- Small independently verifiable work units.
- Critique for scope creep and weak evidence.
- Explicit remote-mutation approval.
- Local validation and final diff review.
- Honest passed / failed / skipped / unavailable results.
- Resumable handoff with exact next action.

### SIMPLIFY

| Original | FPAT Lite |
|---|---|
| `/fpat-prime` scans required GitHub surfaces | `prime` inspects only relevant available sources |
| V1 → three research passes → five-dimension score | Brainstorm and research only when a choice needs them |
| Seven-dimension direction scoring | Short evidence-based trade-off table |
| Initiative → umbrella → epic → sub-issue | Goal → task → practical checklist |
| Exactly five sub-issues | Two to seven when useful; no fixed number |
| One branch/PR per mandatory sub-issue | One coherent local change; repository delivery policy decides Git |
| Platform-owned handoff path | `.fpat/handoff.md` shared by all agents |
| Many rule files and giant prompts | Three shared rule documents and six command contracts |

### MAKE OPTIONAL

- GitHub issues as task storage.
- Branch and pull-request templates.
- Conventional commits and squash merge.
- Project v2 boards.
- Label-to-field synchronization.
- Parent rollup enforcement.
- Scheduled blocked-item or invariant audits.
- External code-review and security services.
- CI that runs FPAT Lite self-validation.
- Formal decision records for durable architectural choices.

### REMOVE FROM THE CORE

- Mandatory umbrella/foundation/parallel/release hierarchy.
- Mandatory exactly-five decomposition.
- Fixed score bands and promotion thresholds.
- Required personal access tokens and dual-token architecture.
- Required Project fields, label taxonomy, or hardcoded workflow names.
- Automatic board writes, issue creation, closure, reopening, or comments.
- Mandatory weekly cron.
- Named third-party checks.
- Multi-agent roles created only for appearance.
- Dashboards, databases, services, and custom orchestration.

## Resulting invariant

FPAT Lite preserves the control loop:

```text
context → choice → evidence-backed plan → scoped change → executed evidence → resume
```

It removes the assumption that this loop must be represented by a large GitHub
issue tree and board automation.

