# E04 — DistilBERT training and immutable artifact


## Migration identity

- Canonical identifier: `E04` (GitHub issue type: epic).
- Legacy identifier: `U04` (retained as `old_identifier`).
- Parent umbrella: `W02`.
- Milestone: `M1 — IntentGuard Weekend MVP`.
## Objective

Fine-tune one 77-class DistilBERT model, select confidence threshold from validation predictions only, and save a reloadable immutable artifact with full provenance.

## Rationale

This is the improved model and the single deployable unit shared by final evaluation and serving.

## Parent identifier

Umbrella issue `W02` in milestone `M1 — IntentGuard Weekend MVP`.

## Source task

T-004.

## Traceability

Primary: T-004, FR-003, FR-004, FR-008, NFR-001, AC-003, AC-005, AC-010.

## Prerequisites

U01–U03 complete; immutable base-model revision verified; memory smoke test passes; training configuration and threshold rule are frozen.

## Likely files

`configs/default.toml`, `src/intentguard/training.py`, `src/intentguard/threshold.py`, `src/intentguard/artifacts.py`, `scripts/train_transformer.py`, `tests/unit/test_threshold.py`, `tests/unit/test_artifacts.py`, `tests/integration/test_training_smoke.py`.

## Implementation boundary

One `distilbert-base-uncased` sequence classifier. `make train` owns validation predictions and threshold selection; test labels are inaccessible to that selection path. Artifact directories are immutable after completion.

## MUST scope

S04.1 environment/forward smoke; S04.2 deterministic fine-tuning and validation predictions; S04.3 threshold selection, immutable artifact, and reload parity.

## Explicit non-goals

Alternative transformer architectures, search sweeps, distillation, quantization, ONNX, per-class thresholds, test-set threshold selection, or serving.

## Acceptance criteria

Fine-tuning completes; the artifact contains weights, tokenizer, label mapping, config, revisions, seeds, dependency provenance, validation-selected threshold and objective; reload produces parity; test labels never affect the threshold.

## Validation commands

`make train && uv run pytest tests/unit/test_threshold.py tests/unit/test_artifacts.py tests/integration/test_training_smoke.py -q`.

## Expected evidence

Training/validation logs, immutable artifact identifier, validation prediction summary, threshold provenance, checksums, metadata schema, and reload-parity tests.

## Fallback and status consequence

Smaller batch or CPU execution can remain Implemented when behavior is unchanged. One epoch can count only if genuine fine-tuning completes and required claims are Measured. Frozen embeddings plus logistic regression makes FR-003 Partial and fails strict MVP.

## Stop condition

Stop for base-revision ambiguity, memory failure after safe batch reduction, test leakage, artifact mutation, missing provenance, or reload divergence.

## Definition of ready

U02 data and U03 baseline are Measured; revisions and training parameters are frozen; smoke-test hardware path is identified.

## Definition of done

S04.1–S04.3 pass, artifact and threshold are reloadable and immutable, and all U04 MUST capabilities are Implemented with applicable evidence Measured.

## Labels

`type:epic`, `priority:MUST`, `area:model`

## Estimate

3.0 hours excluding training wall time.
