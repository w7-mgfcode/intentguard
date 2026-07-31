# U08 — Documentation and recruiter-ready delivery

## Objective

Publish concise documentation that lets a reviewer understand, reproduce, operate, verify, and demonstrate exactly what IntentGuard implements and measures.

## Rationale

The portfolio value depends on clarity and honesty as much as code: results, constraints, fallbacks, and operating steps must agree with executed evidence.

## Parent identifier

Master issue `[MVP] Deliver IntentGuard Weekend MVP`.

## Source task

T-008.

## Traceability

Primary: T-008, NFR-010. Secondary documentation supports AC-013 and AC-014 without owning them.

## Prerequisites

U01–U07 outputs, final artifact/report identifiers, and actual validation results.

## Likely files

`README.md`, `docs/OPERATIONS.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/LIMITATIONS.md`, demonstration documentation, and links to generated reports.

## Implementation boundary

Summarize and link to the authoritative specification and real outputs. Do not copy the complete specification or hand-edit metric values independently of reports.

## MUST scope

C08.1 recruiter-facing README; C08.2 operations/status/limitations; C08.3 five-minute delivery path and final consistency review.

## Explicit non-goals

Marketing claims beyond evidence, optional deployment tutorials, duplicate design documents, speculative charts, or screenshots from mocked behavior.

## Acceptance criteria

A new reviewer can install, run commands, locate evidence, understand the threshold lifecycle and API, reproduce the real demo, distinguish implemented/planned/degraded work, and see explicit limitations within five minutes.

## Validation commands

`uv run python scripts/validate_foundation.py && uv run python scripts/validate_acceptance.py && make demo`.

## Expected evidence

Valid local links, command examples matching the Makefile, metrics sourced from reports, implementation-status table matching acceptance evidence, limitations, and a real-artifact demo script/transcript.

## Fallback and status consequence

If metrics or demo evidence are unavailable, document them as unavailable; do not substitute invented or mocked results. Missing required documentation makes U08 Partial and strict MVP fails.

## Stop condition

Stop for copied specification drift, stale commands, unsupported claims, fake evidence, broken links, or contradictions with the status/acceptance report.

## Definition of ready

U07 evidence is stable and every published claim has a declared source.

## Definition of done

C08.1–C08.3 pass, documentation is internally consistent and concise, and the repository is ready for an honest recruiter review.

## Labels

`type:umbrella`, `priority:MUST`, `area:documentation`

## Estimate

1.5 hours.
