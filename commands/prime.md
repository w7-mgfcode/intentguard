# Prime

## Name

`prime`

## Purpose

Capture a concise, read-only repository baseline before planning or editing.

## When to use

Use at session entry, after a long pause, after switching repositories, or when
the current branch, instructions, task state, or handoff is uncertain.

## Required inputs

- Repository working directory.
- The user's current objective, if one was supplied.

## Optional inputs

- Issue or pull-request number or URL.
- Scope path.
- Existing `.fpat/handoff.md`.

## Files to read

1. Instruction files discovered for the current agent.
2. `AGENTS.md`, `CLAUDE.md` when applicable, and linked core rules.
3. Repository README and build metadata relevant to the task.
4. `.fpat/handoff.md` and `.fpat/plan.md` when present.
5. Only the code and tests needed to understand the active area.

## Allowed tools

- File listing and text search.
- Read-only file inspection.
- Read-only Git commands.
- Read-only GitHub CLI commands when authenticated and relevant.
- Official documentation search for a material current uncertainty.

## Read-only operations

Typical operations include:

```sh
git status --short --branch
git log -5 --oneline
git diff --stat
gh repo view --json nameWithOwner,visibility,defaultBranchRef,pushedAt
gh issue list --state all --limit 50
gh pr list --state all --limit 30
gh workflow list
```

Run only commands supported by the environment. Do not read secrets or broad
unrelated directories.

## Mutation boundary

No file edits, dependency installation, branch changes, commits, pushes,
GitHub writes, workflow dispatches, or cleanup operations.

## Step-by-step procedure

1. Locate the repository root and active instruction files.
2. Read the smallest relevant instruction chain.
3. Inspect branch, worktree status, recent history, and current diff summary.
4. Detect the stack from checked-in build and dependency files.
5. Read any active plan or handoff.
6. Inspect relevant live GitHub state only when it affects the request.
7. Identify conflicts, missing context, user changes, and approval-sensitive
   actions.
8. Produce the baseline report and recommend one next command.

## Expected output

```text
Repository summary
Relevant instructions
Current Git state
Detected stack
Active task
Known constraints
Risks or missing context
Recommended next action
```

Keep the report concise and distinguish observed facts from inference.

## Validation checklist

- [ ] No mutation occurred.
- [ ] Active instructions were identified.
- [ ] User changes were not mistaken for agent changes.
- [ ] Git state and stack claims cite inspected evidence.
- [ ] Missing access or context is explicit.
- [ ] Exactly one next command is recommended.

## Stop conditions

Stop when the repository cannot be resolved, required paths are inaccessible,
instructions materially conflict, or safe inspection would expose secrets.

## Failure handling

Report the failed inspection, the exact missing evidence, and what the user can
provide. Continue with verified local facts when the missing source is
non-blocking.

## Example invocation

```text
$fpat-lite prime focus on the API package
```

## Example response

```text
Repository: small Python API on branch feature/health.
Instructions: root AGENTS.md plus FPAT Lite core and safety rules.
Git state: two pre-existing modified test files; no FPAT edits.
Stack: FastAPI and pytest, inferred from pyproject.toml.
Risk: the requested response schema is not defined.
Next: brainstorm if schema choice is open; otherwise plan.
```

