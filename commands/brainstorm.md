# Brainstorm

## Name

`brainstorm`

## Purpose

Frame the problem, compare a few realistic solutions, and resist unnecessary
complexity before choosing an implementation direction.

## When to use

Use when requirements permit materially different approaches, a design choice
has meaningful trade-offs, or the first idea may be overengineered.

## Required inputs

- Problem or desired outcome.
- Known repository constraints.

## Optional inputs

- Time budget.
- Preferred technologies.
- Explicit non-goals.
- Evaluation criteria.

## Files to read

- Active repository instructions and core rules.
- Relevant architecture and dependency files.
- Existing request, plan, or decision record.
- `templates/brainstorm.md` when a persistent artifact is requested.

## Allowed tools

- Read-only repository inspection.
- Focused official documentation or primary-source research.
- Local calculation needed to compare options.

## Read-only operations

Inspect existing patterns, dependencies, tests, and relevant history. Research
only uncertainties that could change the recommendation.

## Mutation boundary

Default to a conversational result. Write `.fpat/brainstorm.md` only when the
user requests a saved artifact. Do not edit product code or mutate remote
systems.

## Step-by-step procedure

1. Restate the problem and desired outcome.
2. Separate known facts, assumptions, and open questions.
3. Define the criteria that matter for this decision.
4. Produce three to five viable options, including a deliberately simple one.
5. Compare value, complexity, risks, reversibility, validation effort, and fit
   with existing repository conventions.
6. Research only decision-critical uncertainty.
7. Recommend one option and explain why the added complexity, if any, pays for
   itself.
8. Identify questions that block planning; omit questions that do not change
   the design.

## Expected output

```text
Problem framing
Known facts and assumptions
3–5 candidate solutions
Pros and cons
Complexity estimate
Recommended option
Open questions
```

## Validation checklist

- [ ] At least three genuinely distinct options were considered when possible.
- [ ] One option is the simplest adequate solution.
- [ ] Trade-offs use repository evidence rather than generic preference.
- [ ] Research is cited when current external facts matter.
- [ ] Recommendation and unresolved questions are explicit.

## Stop conditions

Stop when the problem itself is undefined, a missing user decision would change
the architecture, or research access is required but unavailable.

## Failure handling

Label provisional assumptions, give a conditional recommendation, and state
what evidence would confirm or reverse it.

## Example invocation

```text
/fpat-lite brainstorm add a health endpoint without adding infrastructure
```

## Example response

```text
Options: a plain route, a route plus dependency probes, or a monitoring
subsystem. The plain route best fits the current API and can be tested without
new dependencies. Dependency probes are deferred until the service has a real
readiness requirement.
```

