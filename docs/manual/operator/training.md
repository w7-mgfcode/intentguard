# Training

Two commands, two sealed bundles: `make baseline` trains and measures the lexical baseline; `make train` fine-tunes DistilBERT, selects the abstention threshold from validation predictions only, and seals both into one immutable artifact.

**Purpose:** what each training command does, what it writes, and where the leakage controls sit in the sequence.
**Intended reader:** operators producing artifacts; integrators will also want [Artifact format](../integrator/artifact-format.md).

## What you'll accomplish

A sealed baseline bundle under `artifacts/intentguard-baseline/` and a sealed transformer bundle under `artifacts/intentguard-distilbert/` — the two inputs [Evaluation](evaluation.md) requires. Prerequisites: [Preparing data](data.md) has run.

## `make baseline` — the TF-IDF logistic-regression baseline

```bash
make baseline
```

Trains a TF-IDF + logistic-regression classifier (U03) under the frozen `[baseline]` block of `configs/default.toml` — lowercased 1–2‑grams, 50,000 max features, sublinear TF, `lbfgs`, balanced class weights ([Configuration reference](../configuration.md)). The command trains, persists the bundle, **reloads it from disk**, and measures the reloaded copy — so the recorded metrics describe the artifact a consumer would actually load, not the in-memory model that produced it. The recorded run measured test accuracy 0.8653 and macro-F1 0.8654 ([IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md), U03 row — including why this command reading the test split is documented divergence D1, required by AC-002).

The baseline bundle carries no threshold and no validation metrics; those belong to the transformer bundle. Both bundles share one schema — the threshold files are optional by design.

## `make train` — DistilBERT plus the sealed threshold

```bash
make train
```

Fine-tunes `distilbert/distilbert-base-uncased` (pinned at revision `12040accade4e8a0f71eabdb258fecc2e7e948be`) for two epochs on CPU under the frozen `[training]` block: sequence length 96, batch size 16, learning rate 2e-5, weight decay 0.01, warmup ratio 0.1 (U04). The device is fixed to CPU by decision — auto-selecting CUDA when present would make a recorded run unreproducible on the machine that validated it.

Then the step that defines the system: **threshold selection** (FR-004, AC-005). From validation predictions only, the selector enumerates every candidate threshold (each unique observed validation confidence, plus 0.0 and 1.0), discards candidates whose coverage falls below `minimum_coverage = 0.70`, and picks the lowest selective risk — ties broken by higher coverage, then lower threshold, so identical inputs always select the identical value. The selection function structurally cannot receive test data: its API accepts only per-item confidence and correctness. The recorded run selected `0.16841767053420467` at validation coverage 0.7015, accepted accuracy 0.8395, selective risk 0.1605.

The threshold, its selection rule (`min_selective_risk_at_min_coverage`, version 1), its source (`validation`), and the validation evidence behind it are sealed into the bundle as `threshold.json`. Every later consumer — evaluation, serving — loads this value and applies it unchanged; a bundle whose threshold source is anything but `validation` is refused at load ([Artifact format](../integrator/artifact-format.md)).

**Expect this to take a while on CPU** — it is a genuine two-epoch fine-tune, not a shortcut. No test-split example or label is read anywhere in `make train`; the U04 status row consequently has no test metric, on purpose.

## Bundle reuse instead of retraining

The bundle's identity — its `run_id`, e.g. `intentguard-distilbert-1fb62b1bb463-88e538757339` — is derived from the dataset revision and the configuration, never from wall-clock time. When `make train` finds a bundle whose content-derived run ID already exists, it **reuses that bundle and rebuilds only the report** instead of retraining. Consequences worth knowing:

- Re-running `make train` unchanged is cheap and cannot fork your artifacts.
- Changing any `[training]` or `[threshold]` value produces a *new* run ID and a *sibling* bundle. The old one is not deleted — and [Evaluation](evaluation.md) will then refuse to run until exactly one bundle remains per artifact directory. Remove the superseded one deliberately; nothing removes it for you.
- A published bundle is never overwritten. Immutability is enforced by the artifact layer, not by convention.

## Where the leakage controls sit

| Control | Enforced at |
|---|---|
| Validation derived from source train only | data preparation ([Preparing data](data.md)) |
| Hyperparameters frozen before test is read | `configs/default.toml`, validated at load |
| Threshold selected from validation only | selection API — no parameter can carry test data (AC-005) |
| Threshold source re-checked at every load | artifact layer and serving boundary (FR-006) |
| Evaluation applies, never reselects | `make evaluate` imports no selection or fitting function |

## Next

[Evaluation](evaluation.md) — compare both sealed bundles on the untouched test split.
