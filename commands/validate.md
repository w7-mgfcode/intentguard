# Validate

## Name

`validate`

## Purpose

Produce honest, reproducible evidence about the change and its acceptance
criteria.

## When to use

Use after implementation, before handoff or delivery, when a regression is
suspected, or when previous validation evidence is stale.

## Required inputs

- Change or behavior to validate.
- Acceptance criteria or expected behavior.

## Optional inputs

- Scope path.
- Approved validation commands.
- Time limit.
- Prior `.fpat/validation.md`.

## Files to read

- Active instructions.
- Changed files and relevant tests.
- Project build and test configuration.
- Plan acceptance criteria.
- `templates/validation-report.md` when saving evidence.

## Allowed tools

- Read-only file and Git inspection.
- Project-defined test, lint, format-check, type-check, build, and smoke-test
  commands.
- Temporary local outputs created by those commands.

## Read-only operations

Inspect the diff, configuration, test selection, and prior results. Prefer
check-only formatter modes and disposable test environments.

## Mutation boundary

Do not edit product code during validation. If a failure needs a fix, report it
and return to `implement`. Write `.fpat/validation.md` only when requested.
Never dispatch remote workflows or change remote state without explicit
approval.

## Step-by-step procedure

1. Translate each acceptance criterion into observable evidence.
2. Identify the smallest sufficient validation set.
3. Run syntax or static checks.
4. Run targeted tests.
5. Run broader tests or a build when applicable and affordable.
6. Perform a focused smoke test when it proves behavior not covered elsewhere.
7. Inspect `git diff --check`, final diff scope, and generated artifacts.
8. Classify every check as passed, failed, skipped, or unavailable.
9. Map results back to acceptance criteria.
10. Recommend delivery, repair, or additional evidence.

## Expected output

```text
Validation scope
Environment
Commands executed
Passed
Failed
Skipped
Unavailable
Acceptance criteria mapping
Residual risk
Verdict
```

## Validation checklist

- [ ] Every pass claim comes from an executed successful command.
- [ ] Failures include actionable evidence.
- [ ] Skipped and unavailable checks are distinct.
- [ ] Acceptance criteria are explicitly mapped.
- [ ] Diff scope and whitespace errors were inspected.
- [ ] Residual risk is honest.

## Stop conditions

Stop when a check is destructive, requires production data, needs missing
credentials, would mutate a remote system, or exceeds the agreed time or
resource limit.

## Failure handling

Capture the command, exit status, and concise error. Do not rerun indefinitely,
hide output, alter tests, or call the task complete. Recommend `implement` for
the smallest justified repair.

## Example invocation

```text
$fpat-lite validate the health endpoint against the approved criteria
```

## Example response

```text
Passed: targeted endpoint tests, full local test suite, and diff whitespace
check. Skipped: deployment probe because no deployment is in scope. Verdict:
the local acceptance criteria are satisfied; remote delivery was not attempted.
```

