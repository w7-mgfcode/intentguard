# E03 — TF-IDF logistic-regression baseline


## Migration identity

- Canonical identifier: `E03` (GitHub issue type: epic).
- Legacy identifier: `U03` (retained as `old_identifier`).
- Parent umbrella: `W02`.
- Milestone: `M1 — IntentGuard Weekend MVP`.
## Objective

Train, persist, reload, and measure one deterministic scikit-learn TF-IDF logistic-regression baseline using the U02 contract.

## Rationale

A credible lexical baseline makes transformer improvement measurable and provides an early working checkpoint.

## Parent identifier

Umbrella issue `W02` in milestone `M1 — IntentGuard Weekend MVP`.

## Source task

T-003.

## Traceability

Primary: T-003, FR-002, AC-002.

## Prerequisites

U01 complete and U02 pinned data outputs available.

## Likely files

`src/intentguard/baseline.py`, `src/intentguard/metrics.py`, `src/intentguard/artifacts.py`, `scripts/train_baseline.py`, `tests/unit/test_baseline.py`, `tests/unit/test_metrics.py`, baseline artifact/report paths.

## Implementation boundary

One explicitly configured TF-IDF plus logistic-regression pipeline; shared splits, labels, seeds, and metric code; no baseline tuning on test.

## MUST scope

S03.1 pipeline and fit; S03.2 artifact reload parity; S03.3 measured report and regression checks.

## Explicit non-goals

Additional classical models, ensembles, hyperparameter search, transformer embeddings, or fabricated performance thresholds.

## Acceptance criteria

`make baseline` fits on training data, uses validation only for allowed choices, evaluates the canonical test split at the declared checkpoint, writes accuracy/macro-F1 and provenance, and reloads with prediction parity.

## Validation commands

`make baseline && uv run pytest tests/unit/test_metrics.py tests/unit/test_baseline.py tests/unit/test_artifacts.py -q`.

## Expected evidence

Serialized pipeline, configuration, data fingerprint, dependency versions, class mapping, deterministic predictions, and measured report.

## Fallback and status consequence

Reduced safe iteration settings may remain Implemented if they preserve the specified estimator and are recorded. A different or unmeasured model is Partial and fails strict MVP.

## Stop condition

Stop for data mismatch, convergence/error instability, artifact reload divergence, test-driven tuning, or missing required metrics.

## Definition of ready

U02 evidence is complete and baseline hyperparameters are explicitly resolved in configuration before fitting.

## Definition of done

S03.1–S03.3 pass and the working-baseline checkpoint is recorded as Implemented and Measured.

## Labels

`type:epic`, `priority:MUST`, `area:baseline`

## Estimate

3.0 hours.
