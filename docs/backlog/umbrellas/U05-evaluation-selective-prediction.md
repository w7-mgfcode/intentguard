# E05 — Comparative evaluation and selective prediction


## Migration identity

- Canonical identifier: `E05` (GitHub issue type: epic).
- Legacy identifier: `U05` (retained as `old_identifier`).
- Parent umbrella: `W02`.
- Milestone: `M1 — IntentGuard Weekend MVP`.
## Objective

Load persisted baseline and transformer artifacts, evaluate them comparably on the untouched test split, and measure calibration, coverage, selective risk, latency, and unsupported-request abstention.

## Rationale

The project’s value is not a model claim alone but transparent evidence for when predictions should be trusted or withheld.

## Parent identifier

Umbrella issue `W02` in milestone `M1 — IntentGuard Weekend MVP`.

## Source task

T-005.

## Traceability

Primary: T-005, FR-005, FR-009, NFR-006, AC-004, AC-011, AC-012.

## Prerequisites

U02 data contract, U03 baseline artifact, and U04 immutable transformer artifact with persisted threshold.

## Likely files

`src/intentguard/evaluation.py`, `src/intentguard/metrics.py`, `scripts/evaluate.py`, `tests/unit/test_metrics.py`, `tests/unit/test_eval_regression.py`, `tests/fixtures/unsupported.json`, `reports/`.

## Implementation boundary

`make evaluate` only loads the persisted threshold; it cannot select or update it. Both models use the same test rows, labels, and metric definitions. Unsupported fixtures are reported separately from BANKING77.

## MUST scope

S05.1 comparable classification results; S05.2 calibration, coverage/selective risk, and latency; S05.3 unsupported fixture report and report-schema validation.

## Explicit non-goals

Temperature scaling, charts without real metrics, extra OOD datasets, threshold retuning, statistical overclaims, or model changes.

## Acceptance criteria

The report shows required metrics for both models, verifies transformer improvement where required, applies the persisted threshold exactly, reports calibration convention, coverage/risk tradeoff, latency environment, and unsupported fixture results separately.

## Validation commands

`make evaluate && uv run pytest tests/unit/test_metrics.py tests/unit/test_threshold.py tests/unit/test_eval_regression.py -q`.

## Expected evidence

Versioned machine-readable report tied to data and artifact IDs, metric regression tests, threshold identity proof, declared ECE binning/tolerances, latency samples, and separate unsupported-request table.

## Fallback and status consequence

CPU-only evaluation is Implemented when environment and timings are reported. Missing comparison, calibration, selective evidence, or real artifacts makes U05 Partial/Blocked and fails strict MVP.

## Stop condition

Stop for test-driven selection, data/artifact mismatch, incomparable preprocessing, undefined metric convention, empty fixtures, or invented/unstable evidence.

## Definition of ready

U03 and U04 artifacts pass reload tests; metric definitions, ECE binning, numerical tolerances, fixture semantics, and latency protocol are resolved.

## Definition of done

S05.1–S05.3 pass and all required evaluation claims are Measured from the declared immutable inputs.

## Labels

`type:epic`, `priority:MUST`, `area:evaluation`

## Estimate

2.0 hours.
