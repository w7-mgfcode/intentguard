# Plan

## Name

`plan`

## Purpose

Turn a selected direction into a proportionate, evidence-backed, verifiable
implementation plan.

## When to use

Use before a multi-file or behavior-changing implementation, when acceptance
criteria need clarification, or when dependencies and rollback deserve explicit
thought.

## Required inputs

- Selected direction or requested outcome.
- Current repository baseline.

## Optional inputs

- Time or scope limit.
- Issue reference.
- Required delivery format.
- Existing brainstorm or prior plan.

## Files to read

- Active instructions and core rules.
- Relevant code, tests, configuration, and documentation.
- `.fpat/brainstorm.md` or `.fpat/handoff.md` when present.
- `templates/implementation-plan.md` when saving the plan.

## Allowed tools

- Read-only repository and Git inspection.
- Read-only GitHub inspection.
- Focused primary-source research.
- Local calculations or disposable experiments that do not alter the
  repository; disclose them.

## Read-only operations

Trace current behavior, affected boundaries, dependencies, validation commands,
and rollback options. Confirm current library or platform behavior when it is a
material dependency.

## Mutation boundary

Do not edit product code or remote systems. Write `.fpat/plan.md` only when the
user asks for a persistent plan. Planning does not authorize later GitHub
writes.

## Step-by-step procedure

1. Confirm the objective and current behavior.
2. List known facts, labeled assumptions, and decision-critical unknowns.
3. Research material unknowns using primary sources.
4. Define in-scope and out-of-scope work.
5. Write observable acceptance criteria.
6. Identify files likely affected and dependencies between steps.
7. Use the smallest number of independently verifiable steps, normally two to
   seven.
8. Define validation for each step and the final change.
9. Identify risks, rollback or recovery, and approval-sensitive operations.
10. Critique the plan for duplication, unrelated refactoring, hidden
    infrastructure, and unsupported assumptions.
11. Present the revised plan without starting implementation.

## Expected output

```text
Objective
Context and evidence
Assumptions
Scope / out of scope
Research findings
Acceptance criteria
Affected files
Ordered steps
Risks and recovery
Validation strategy
Approval-sensitive operations
```

## Validation checklist

- [ ] The plan is proportionate to the task.
- [ ] Acceptance criteria are observable.
- [ ] Each step has a validation method.
- [ ] External mutations are separated and named.
- [ ] Research claims have primary-source citations.
- [ ] The plan can be executed without redesigning it.

## Stop conditions

Stop when a missing decision changes public behavior, data loss risk, security,
cost, or external authority.

## Failure handling

Provide the smallest safe partial plan, label blocked steps, and ask only the
question needed to unlock the next decision.

## Example invocation

```text
$fpat-lite plan selected option: plain /health endpoint returning service state
```

## Example response

```text
1. Add a response model and GET /health route in src/api.py.
2. Add success and method tests in tests/test_health.py.
3. Run targeted pytest, then the full available suite and diff checks.
Out of scope: database probes, authentication, dashboards, deployment.
```

