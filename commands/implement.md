# Implement

## Name

`implement`

## Purpose

Make one requested, coherent local change and validate it without unrelated
refactoring or silent remote actions.

## When to use

Use when the user has requested implementation and the objective, scope, and
acceptance criteria are clear enough to change files safely.

## Required inputs

- Requested change.
- Observable acceptance criteria.
- Repository working directory.

## Optional inputs

- Approved `.fpat/plan.md`.
- Issue reference.
- Scope path.
- Time box.

## Files to read

- Active instructions and all files directly affected.
- Relevant tests and build configuration.
- Approved plan or handoff when present.
- `rules/engineering-and-validation.md`.

## Allowed tools

- Local file inspection and editing.
- Project-provided formatter, linter, type checker, build, and tests.
- Read-only Git and GitHub inspection.
- Focused official documentation for an implementation blocker.

## Read-only operations

Inspect current behavior, history where useful, user changes, dependencies, and
the final diff. Read-only remote inspection remains allowed.

## Mutation boundary

The implementation request authorizes the smallest necessary local file
changes. It does not authorize commits, pushes, issue edits, pull-request
creation, merges, workflow dispatches, releases, Project changes, or other
remote mutations unless the current request explicitly includes that exact
action.

## Step-by-step procedure

1. Reconfirm scope, acceptance criteria, and current worktree changes.
2. Inspect the implementation and tests before editing.
3. Make the smallest coherent change.
4. Add or update focused tests at the affected boundary.
5. Run the narrowest useful check early.
6. Fix only failures caused by the change; report unrelated failures.
7. Run the applicable final validation set.
8. Review `git diff --check`, the full diff, and unexpected files.
9. Update documentation only when behavior or usage changed.
10. Summarize changes, evidence, limitations, and any pending remote action.

## Expected output

```text
Outcome
Files changed
Key decisions
Checks executed and results
Acceptance criteria status
Known limitations
Pending approvals or next action
```

## Validation checklist

- [ ] User changes were preserved.
- [ ] No unrelated refactor entered the diff.
- [ ] Relevant tests cover the behavior.
- [ ] Executed checks are named with real results.
- [ ] The final diff was inspected.
- [ ] No remote mutation occurred without exact authorization.

## Stop conditions

Stop when implementation would exceed scope, overwrite user work, require a new
architectural decision, need unavailable credentials, perform a destructive
action, or require unapproved remote mutation.

## Failure handling

Preserve the worktree, record the command and failure accurately, distinguish
new from pre-existing failures, and provide the smallest next diagnostic step.
Do not weaken tests merely to obtain green output.

## Example invocation

```text
/fpat-lite implement the approved health endpoint plan
```

## Example response

```text
Added GET /health and its typed response plus two focused API tests. Targeted
tests and the available full suite passed; the final diff contains only the API
and test files. No commit, push, or pull request was created.
```

