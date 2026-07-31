# U06 — FastAPI inference and real-artifact demo

## Objective

Expose typed health and prediction endpoints backed by one real loaded transformer artifact, with stable errors, structured logs, and a five-minute local demonstration.

## Rationale

A narrow production boundary proves artifact reuse and operational behavior without turning the weekend project into a deployment platform.

## Parent identifier

Master issue `[MVP] Deliver IntentGuard Weekend MVP`.

## Source task

T-006.

## Traceability

Primary: T-006, FR-006, FR-007, NFR-004, NFR-005, AC-006, AC-007, AC-008, AC-009, AC-013.

## Prerequisites

U04 immutable artifact and U05 evaluation contract complete; request-ID, tie-breaking, and control-character rules resolved before public contract coding.

## Likely files

`src/intentguard/api.py`, `src/intentguard/schemas.py`, `src/intentguard/predictor.py`, `src/intentguard/logging.py`, `scripts/demo.py`, `tests/contract/test_api_contract.py`, `tests/unit/test_logging.py`, `tests/integration/test_api.py`.

## Implementation boundary

One FastAPI process loads one artifact at startup and never trains. Prediction returns accepted intent or abstention based on the persisted threshold. Deterministic predictors may be injected only in tests or explicitly degraded mode.

## MUST scope

C06.1 schemas, validation, stable errors, request IDs, and safe logs; C06.2 predictor/startup plus health and predict endpoints; C06.3 strict real-artifact demo.

## Explicit non-goals

Batch endpoint, database, authentication platform, ticket adapter, human-review queue, cloud deployment, frontend, or mock-backed strict demo.

## Acceptance criteria

Accepted, abstained, malformed, and health cases match the interface contract; startup fails honestly for invalid artifacts; logs omit raw sensitive text; the demo uses the same real artifact evaluated by U05.

## Validation commands

`uv run pytest tests/contract/test_api_contract.py tests/unit/test_logging.py tests/integration/test_api.py -q && make demo`.

## Expected evidence

Schema snapshots/assertions, sanitized structured logs, artifact identity in health, accepted/abstained responses, deterministic error bodies, and captured real-artifact demo transcript.

## Fallback and status consequence

A deterministic predictor is Mocked and permitted for tests or labelled degraded mode only. If the strict demo or service does not load the real transformer artifact, U06 is Partial/Mocked and strict MVP fails.

## Stop condition

Stop for schema ambiguity, raw text/secrets in logs, artifact mismatch, training in serving, non-deterministic error contract, or mock-only demo.

## Definition of ready

Artifact schema and threshold semantics are stable; request-ID, tie-breaking, input normalization/control-character, and error rules are explicitly decided.

## Definition of done

C06.1–C06.3 pass and the real artifact serves all required contracts and demo cases.

## Labels

`type:umbrella`, `priority:MUST`, `area:api`

## Estimate

2.0 hours.
