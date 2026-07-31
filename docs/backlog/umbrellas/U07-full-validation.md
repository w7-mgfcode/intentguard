# U07 — Full validation and acceptance gate

## Objective

Execute the complete CPU-reproducible validation suite, audit AC-001–AC-014 and strict-MVP status, and produce a truthful completion decision.

## Rationale

Passing isolated features is insufficient; the final repository needs integrated evidence and an explicit honesty gate.

## Parent identifier

Master issue `[MVP] Deliver IntentGuard Weekend MVP`.

## Source task

T-007.

## Traceability

Primary: T-007, NFR-002, NFR-009, AC-014. Secondary verification covers all AC identifiers without changing primary ownership.

## Prerequisites

U01–U06 implementation complete and all generated evidence available from declared commands.

## Likely files

`scripts/validate_acceptance.py`, `tests/`, `Makefile`, `.github/workflows/ci.yml`, `reports/acceptance.json`, `docs/IMPLEMENTATION_STATUS.md`.

## Implementation boundary

Validate and classify existing behavior; do not redesign features, relax MUST criteria, or replace failed evidence with prose.

## MUST scope

C07.1 CPU suite and validation orchestration; C07.2 acceptance/status audit and Sunday completion gate.

## Explicit non-goals

Optional features, load testing, cloud validation, Docker, new metrics, or changing requirements to make checks pass.

## Acceptance criteria

All executable checks are recorded; unavailable checks are distinct; every AC has evidence; each MUST is Implemented; applicable claims are Measured; CI mirrors the valid CPU subset; final status has no contradiction.

## Validation commands

`make setup && make lint && make test && make data && make baseline && make train && make evaluate && make demo` plus `uv run python scripts/validate_acceptance.py`.

## Expected evidence

CPU CI result, local command transcript, `reports/acceptance.json`, requirement-by-requirement status, fallback audit, unresolved-item scan, secret/generated-artifact scan, and Sunday gate verdict.

## Fallback and status consequence

CPU-only execution is valid. Any failed/unavailable MUST acceptance evidence is not passed; affected work is Partial or Blocked and strict MVP fails until corrected.

## Stop condition

Stop completion for any missing AC owner/evidence, false status, failing required check, leaked secret, tracked generated artifact, test-label leakage, or mock replacing a MUST.

## Definition of ready

U01–U06 report done; commands and evidence paths are stable; no known implementation work is disguised as validation.

## Definition of done

C07.1 and C07.2 pass, AC-001–AC-014 have reviewed evidence, and the strict-MVP verdict is explicit and defensible.

## Labels

`type:umbrella`, `priority:MUST`, `area:quality`

## Estimate

1.5 hours.
