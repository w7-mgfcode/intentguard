# Requirements and Acceptance Criteria

## Functional requirements

### FR-001 — Dataset preparation

The system shall download or load a pinned BANKING77 revision, validate its
schema, preserve the upstream train/test split, derive a validation split from
training data only, and record dataset metadata.

### FR-002 — Baseline

The system shall train a TF-IDF plus logistic-regression baseline and evaluate
it on the untouched test split.

### FR-003 — Improved model

The system shall fine-tune one `distilbert-base-uncased` sequence-classification
model over the same label space and evaluate it on the same test split.

### FR-004 — Abstention policy

The system shall select and persist a global confidence threshold using
validation predictions only, then return `abstain` when maximum predicted
probability is below that threshold.

### FR-005 — Evaluation

The system shall generate comparable baseline and transformer metrics,
per-class error information, calibration information, risk/coverage data, and
latency measurements without inventing results.

### FR-006 — Inference API

The system shall expose `POST /v1/predict` and return the predicted intent,
confidence, decision, threshold, truncation status, model version, and latency
for valid input.

### FR-007 — Health check

The system shall expose `GET /health` and report readiness only after the model,
label mapping, threshold, and metadata are loaded consistently.

### FR-008 — Artifact persistence

The system shall save and reload model artifacts, label mappings, threshold,
configuration, and provenance metadata from the local filesystem.

### FR-009 — Behavioral unsupported-query fixture

The evaluation shall run a small version-controlled fixture of clearly
unsupported requests and report abstention behavior separately from BANKING77
benchmark metrics.

### FR-010 — Reproducible commands

The repository shall provide documented commands for setup, data preparation,
baseline training, transformer training, evaluation, testing, serving, and
demonstration.

## Non-functional requirements

### NFR-001 — Local compatibility

The complete workflow shall fit within 24 GB system RAM and the available RTX
5060 Mobile GPU. Batch size shall be configurable for lower-memory devices.

### NFR-002 — CPU support

API inference and all critical tests shall run on CPU. Full transformer training
need not meet the weekend time budget on CPU.

### NFR-003 — Reproducibility

The system shall record seeds, package lockfile, model identifier and revision,
dataset identifier and revision, configuration, device, and artifact version.
Exact equality across different hardware is not guaranteed.

### NFR-004 — Input safety

The API shall reject empty text, text longer than 512 characters, malformed
JSON, and unknown request fields with clear 4xx responses.

### NFR-005 — Privacy-conscious logging

INFO logs shall not contain raw request text. Logs may contain request ID,
input length, decision, intent, confidence, model version, latency, and error
category.

### NFR-006 — Performance reporting

The evaluation shall report measured batch conditions and p50/p95 inference
latency. No universal latency service-level claim is permitted.

### NFR-007 — Maintainability

Reusable data, training, evaluation, artifact, and inference logic shall live
in typed Python modules with focused responsibilities.

### NFR-008 — Dependency control

Dependencies shall be declared in `pyproject.toml` and locked with `uv.lock`.
CI shall install from the lockfile.

### NFR-009 — Testability

Metric logic, threshold selection, preprocessing, artifact loading, API
validation, and end-to-end inference shall be testable without retraining the
full model.

### NFR-010 — Honest reporting

Documentation shall distinguish planned, implemented, partial, mocked, and
measured behavior. No metric or result may be fabricated.

## User stories

### US-001

As an ML engineer, I want one command to prepare validated data so that model
experiments use a known schema and split.

### US-002

As an interviewer, I want to compare the transformer against a meaningful
baseline so that “improvement” has an explicit reference point.

### US-003

As a support-platform engineer, I want low-confidence requests to be abstained
so that uncertain automation can be routed to human handling.

### US-004

As a developer, I want to load the saved model through a typed local API so
that training code is separated from inference.

### US-005

As a reviewer, I want machine-readable metrics, provenance, tests, and
limitations so that repository claims can be checked.

## Acceptance criteria

### AC-001 — Data contract

`make data` exits successfully, validates `text` and `label`, confirms exactly
77 unique label names, creates no test-to-train leakage, and writes dataset
metadata.

### AC-002 — Baseline artifact

`make baseline` saves a reloadable baseline artifact and writes test macro-F1,
accuracy, and per-class metrics to a versioned evaluation file.

### AC-003 — Transformer artifact

`make train` produces a reloadable transformer artifact containing model,
tokenizer, label mapping, configuration, provenance, and validation
predictions.

### AC-004 — Fair comparison

`make evaluate` evaluates both approaches against the same test IDs and emits a
table and JSON file. It reports a negative result honestly if the transformer
does not outperform the baseline.

### AC-005 — Threshold selection

Threshold selection uses validation predictions only, enforces configurable
minimum coverage, records the selection rule, and never reads test labels.

### AC-006 — Accepted prediction

For a valid request whose maximum probability is at least the saved threshold,
the API returns HTTP 200, `decision="accept"`, a valid intent, confidence in
`[0,1]`, input-truncation status, and matching artifact metadata.

### AC-007 — Abstained prediction

For a valid request whose maximum probability is below the threshold, the API
returns HTTP 200, `decision="abstain"`, `intent=null`, confidence, threshold,
input-truncation status, and model metadata.

### AC-008 — Invalid input

Empty, oversized, malformed, or extra-field input is rejected with a stable
4xx error schema and does not invoke model inference.

### AC-009 — Readiness

`GET /health` returns ready only when model, tokenizer, 77-label mapping,
threshold, and metadata pass consistency checks.

### AC-010 — Artifact parity

Predictions produced immediately before saving and after reloading match within
the documented numerical tolerance on a fixed fixture.

### AC-011 — Evaluation regression guard

A tiny committed fixture produces known hand-checked metric and threshold
results, preventing silent changes to evaluation semantics.

### AC-012 — Unsupported-query honesty

The separate unsupported-query report labels the fixture as curated and does
not present its abstention rate as general OOD performance.

### AC-013 — Local demonstration

`make demo` checks health and exercises one accepted and one abstained response
without relying on paid or managed services.

### AC-014 — Validation gate

`make lint` and `make test` pass; the final README contains measured values only
after evaluation artifacts exist.

## Edge cases

- Whitespace-only and control-character-heavy text.
- Valid Unicode and contractions.
- Text exactly at the 512-character boundary.
- Extremely low or exactly equal-to-threshold confidence.
- Label-map mismatch between model configuration and metadata.
- Missing or corrupt threshold/artifact files.
- CPU-only execution.
- CUDA out-of-memory during training.
- Dataset or model download unavailable.
- Multiple predictions with numerically tied probabilities.

## Explicit out-of-scope items

- Multilingual requests and translation.
- Multi-label or hierarchical intent classification.
- Conversation history.
- General-purpose OOD benchmark.
- Per-class thresholds in the guaranteed MVP.
- Temperature scaling in the guaranteed MVP.
- Explanation generation.
- Persistent request storage.
- Cloud, Docker, GPU CI, authentication, rate limiting, autoscaling, dashboards,
  tracing, registry, queue, cache, or database.
