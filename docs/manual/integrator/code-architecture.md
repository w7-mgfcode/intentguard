# Code architecture

A module-by-module tour of `src/intentguard/`: what each file owns, what it deliberately does not, and how a request or a training run flows through them.

**Purpose:** orient an integrator in the codebase fast enough to make a correct change.
**Intended reader:** integrators and contributors. Component boundaries are specified in [ARCHITECTURE.md](../../specification/docs/ARCHITECTURE.md); this chapter maps them to the files as built.

## What you'll accomplish

Given any behavior in this manual, you can name the module that owns it — and, just as usefully, the modules that are *forbidden* from owning it. The codebase's defining pattern is negative space: nearly every module docstring states what the module refuses to do, and those refusals are the leakage and honesty controls.

## The package, grouped by concern

**Configuration and contracts**

- `config.py` — typed loading of `configs/default.toml` into frozen dataclasses, with allow-listed choices and cross-checks against the pinned dataset and base-model constants. One function, `training_config_from_payload`, validates a training block *from anywhere* — the same validators run on the TOML file and on the `config.json` sealed inside an artifact, which is how a hand-edited bundle claiming `threshold_source = "test"` gets refused at load.
- `schemas.py` — the data-contract records (frozen dataclasses) and the Pydantic API models. The API models encode [INTERFACE_CONTRACT.md](../../specification/docs/INTERFACE_CONTRACT.md) exactly: post-strip length bounds, `extra="forbid"`, and the `intent`↔`decision` coupling validated on the response itself (NFR-004).

**Data**

- `data.py` — pinned BANKING77 loading, canonical-label validation (all 77, in order, hash-checked), the deterministic validation carve-out from source train only, split fingerprints, and provenance generation ([Preparing data](../operator/data.md)).

**Models**

- `baseline.py` — builds, fits, and predicts a scikit-learn TF-IDF + logistic-regression `Pipeline` from a validated `BaselineConfig`. Computes no metrics, performs no file I/O. Only stock scikit-learn estimators appear: a custom estimator class would be pickled by reference to this module, so any later rename would silently break every previously saved artifact.
- `training.py` — DistilBERT mechanics: loading (local-files-only readers used by serving too), batching, a plain PyTorch optimisation loop, and shared inference primitives (`predict_probabilities`, argmax/max helpers). `transformers.Trainer` is deliberately absent — it would require `accelerate`, which is not in `uv.lock` (decision D9) — and the device is fixed to CPU (decision D10). No file I/O, no threshold selection, no metrics.

**Decision policy**

- `threshold.py` — pure validation-only threshold selection: candidate enumeration, the coverage-floor + min-selective-risk rule, and `decide(confidence, threshold)`. No file I/O, no model imports; the API accepts only per-item confidence and correctness, so a test label structurally cannot reach it (AC-005). `decide` is the *single* definition of the accept boundary, shared by training, evaluation, and serving, so an exactly-at-threshold confidence cannot be resolved differently in two places.

**Metrics and measurement**

- `metrics.py` — pure, versioned classification metrics shared by evaluation and reporting.
- `latency.py` — the descriptive latency protocol (NFR-006, decision D16): seeded sampling of real test rows (so padding-to-longest measures real length variation, not one literal's length), warm-up discard, environment capture.
- `unsupported.py` — the curated fixture's schema, its six declared categories (a row outside the set is rejected, not counted under an ad-hoc name), the no-collision-with-BANKING77 rule, and the separately labelled report (FR-009, AC-012).
- `evaluation.py` — the equivalence gate that makes the two-model comparison meaningful (FR-005, AC-004): dataset revision, ordered label map, split fingerprints, and the hash of the evaluated test example IDs must all agree before a single prediction is made.

**Serving**

- `api.py` — the HTTP contract and nothing else: validation, the single error envelope, request IDs, text-free log events. It never imports a concrete predictor; it declares a structural `Predictor` protocol and answers `MODEL_NOT_READY` until one is installed via `set_predictor`. The contract is therefore testable before any weights exist.
- `predictor.py` — fills that seam with the real artifact: single-bundle location, checksum re-verification, label-map and threshold validation, and per-request inference through the *shared* primitives, so serving cannot disagree with evaluation about a decision ([Serving](../operator/serving.md)).
- `app.py` — the entry point (`python -m intentguard.app`): resolves `INTENTGUARD_*` settings, configures logging, loads the predictor eagerly (so startup fails before the port binds), and hands off to Uvicorn. The module that resolves environment variables to decide how the serving process starts. `predictor.py` separately reads `INTENTGUARD_ARTIFACT_ROOT` as a bundle-location override, and `scripts/demo.py` / `scripts/validate_acceptance.py` read their own `INTENTGUARD_*` variables outside serving startup.
- `logging.py` — structured serving events with an enforced field list. `PredictionEvent` has no text field at all — it carries `input_characters`, a length — so raw request text cannot enter a log record even by mistake (NFR-005).

## Two flows through the package

**A prediction request:** `app.py` (startup, once) → `api.py` middleware assigns the request ID → `schemas.PredictRequest` validates → `predictor.predict` → `training.predict_probabilities` (eval mode, no-grad, softmax with row-sum check) → `threshold.decide` → `schemas.PredictResponse` validates the outgoing invariants → `logging.log_event`.

**A training run:** `scripts/train_transformer.py` orchestrates: `config.py` loads the frozen block → `data.py` provides validated splits → `training.py` fine-tunes → validation predictions → `threshold.select_threshold` → `artifacts.save_artifact` seals weights + threshold + provenance atomically. The script owns sequencing; the modules stay individually testable.

## The orchestration layer: `scripts/`

Each Make target wraps one script ([Quickstart](../operator/quickstart.md)): `prepare_data.py`, `train_baseline.py`, `train_transformer.py`, `evaluate.py`, `demo.py`, plus the two validators `validate_foundation.py` and `validate_acceptance.py`. Scripts orchestrate and write files; `src/intentguard/` modules compute. The one deliberate inversion: `artifacts.py` owns all bundle I/O so that immutability is a property of the artifact layer, not of each caller's discipline ([Artifact format](artifact-format.md)).

## Next

[Artifact format](artifact-format.md) — the sealed bundle those flows produce and consume.
