# Engineering and validation

**Purpose:** Keep changes small, reviewable, reproducible, and honestly tested.

**Intended reader:** Implementers and reviewers.

**Consult this when:** Editing files, selecting checks, reviewing a diff, or
preparing delivery evidence.

## Before editing

- Confirm repository root, current branch, and worktree state.
- Identify pre-existing user changes and preserve them.
- Read affected implementation, tests, and configuration.
- Confirm scope, acceptance criteria, and out-of-scope work.
- Prefer existing dependencies and patterns.

## While editing

- Make the smallest coherent change.
- Avoid style churn, broad renames, speculative abstractions, and unrelated
  dependency upgrades.
- Keep public behavior, error handling, and compatibility explicit.
- Add comments for non-obvious reasoning, not to narrate obvious code.
- Update documentation when externally visible behavior or usage changes.
- Do not replace meaningful tests with weaker assertions.

## Dependency changes

Add or update a dependency only when it is necessary for the requested outcome.
Record:

- why existing code or standard library is insufficient;
- runtime versus development scope;
- compatibility and license considerations;
- lockfile impact;
- validation performed.

Ask before adding a production dependency when repository instructions do not
already authorize it.

## Validation selection

Choose checks from the repository's own commands:

1. Syntax or parser validation.
2. Formatter check, not rewrite, when available.
3. Lint and type checks relevant to changed files.
4. Focused unit or integration tests.
5. Broader suite or build when proportionate.
6. Smoke test that demonstrates the acceptance criterion.
7. `git diff --check` and final diff inspection.

Do not chase a coverage percentage that adds no decision value.

## Evidence vocabulary

Use exactly these result classes:

- **Passed:** the command executed successfully.
- **Failed:** the command executed and returned failure or incorrect behavior.
- **Skipped:** the check was intentionally not run, with a reason.
- **Unavailable:** the environment lacked a required tool, service, credential,
  or resource.

“Looks correct,” “should pass,” and prior results are not current passes.

## Failure discipline

- Capture the command and concise relevant output.
- Distinguish failures caused by the change from pre-existing failures.
- Do not hide failing output or loop indefinitely.
- Do not modify unrelated files to make a broad suite green.
- Return to `implement` for a justified repair; keep `validate` read-only.

## Git discipline

- Review `git status`, `git diff --stat`, the full diff, and
  `git diff --check`.
- Do not discard or overwrite user changes.
- Do not commit unless requested or clearly included in the task.
- Do not push without exact current authorization.
- When a PR is requested, ensure its summary and checks match actual evidence.
- Closing keywords such as `Closes #N` have remote effects after merge; use
  them intentionally.

## Completion gate

Delivery is ready only when requested behavior exists, applicable checks have
real results, acceptance criteria are mapped, diff scope is understood,
limitations are disclosed, and pending remote actions remain separately
approved.

