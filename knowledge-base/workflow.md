# FPAT Lite workflow

**Purpose:** Explain command selection, transitions, artifacts, and resumption.

**Intended reader:** A developer or agent deciding what to do next.

**Consult this when:** The current mode is unclear or a task is changing phases.

## Lifecycle

```text
Understand request
→ prime repository context
→ brainstorm only when choices matter
→ research decision-critical uncertainty
→ plan proportionately
→ implement one coherent local change
→ validate with executed evidence
→ handoff when work must continue later
```

The arrows are recommendations, not a mandatory state machine. A tiny fix may
use `prime → implement → validate`. A research-only request may stop after
`brainstorm` or `plan`.

## Command selector

| Current question | Command |
|---|---|
| “What repository and task state am I entering?” | `prime` |
| “Which realistic direction should we choose?” | `brainstorm` |
| “How will the selected direction be built and verified?” | `plan` |
| “Please make this clear local change.” | `implement` |
| “What evidence proves the result?” | `validate` |
| “How can another session resume safely?” | `handoff` |

Do not combine `plan` and `implement` when the user requested only a plan. Do
not turn `validate` into an editing loop; return to `implement` for fixes.

## Where research belongs

Research is a supporting activity, not a seventh command:

- During `brainstorm`, research a fact that could change the recommended option.
- During `plan`, research an API, library, standard, or platform behavior that
  affects the implementation.
- During `implement`, research only an unexpected blocker.

Prefer current official documentation, specifications, upstream repositories,
or primary research. Record the finding and its design consequence. Do not
collect links that do not affect a decision.

## Planning scale

| Change size | Suitable plan |
|---|---|
| One obvious file and test | A few bullets in the response |
| Two to five connected files | Short `.fpat/plan.md` with criteria and steps |
| Cross-cutting or risky change | Explicit dependencies, recovery, and approval gates |

Subtasks are practical, independently verifiable units. Two to seven is a
useful range, not a rule. Never manufacture five tasks to satisfy a framework.

## Approval transition

An approved local plan authorizes only what the user requested. If delivery
later needs a push, issue update, pull request, merge, workflow dispatch, or
release, name the exact action and target and obtain current approval.

Remote commands that combine preparation and mutation remain remote writes.
Dry-run labels do not override documented command behavior.

## Resume flow

1. Read `.fpat/handoff.md`.
2. Run `prime`.
3. Compare branch, diff, files, tests, issue/PR state, and approvals with the
   checkpoint.
4. Mark stale claims and re-run evidence when needed.
5. Continue the single recorded next action.
6. Do not inherit old approval when the target or state changed.

## Completion

Finish with a concise outcome:

- what changed or was decided;
- what evidence was executed;
- what failed, was skipped, or was unavailable;
- residual limitations;
- pending approval or next action.

