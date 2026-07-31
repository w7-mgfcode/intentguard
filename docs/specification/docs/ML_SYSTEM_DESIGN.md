# ML System Design

## Problem formulation

Given one English banking-support utterance `x`, estimate:

```text
P(y | x), where y is one of 77 BANKING77 intent labels.
```

The serving decision is:

```text
accept(argmax P(y | x))  if max P(y | x) >= threshold
abstain                   otherwise
```

This is closed-set intent classification with a selective-prediction wrapper.
It is not a general open-set or OOD detector.

## Dataset

- **Source:** `PolyAI/banking77`
- **Task:** English fine-grained banking intent classification
- **Published size:** 13,083 queries across 77 intents
- **Licence:** CC BY 4.0
- **Primary split rule:** preserve the upstream train and test sets
- **Validation:** derive a stratified 15% split from upstream training data
- **Default seed:** 42

The implementation must pin a concrete dataset revision in configuration and
record it in every artifact and evaluation report.

## Small-data strategy

The full dataset is already laptop-sized, so no sampling is needed for the
final evaluation.

A tiny committed fixture is used only for:

- metric unit tests;
- preprocessing tests;
- CPU training smoke tests;
- API integration tests.

The tiny fixture must never be mixed into reported benchmark results.

## Data schema

### Canonical example

```json
{
  "example_id": "train:000001",
  "text": "How do I activate my new card?",
  "label_id": 7,
  "label_name": "activate_my_card",
  "split": "train"
}
```

### Validation rules

- `example_id`: non-empty and unique within the canonical dataset.
- `text`: string, non-empty after trimming.
- `label_id`: integer in `[0, 76]`.
- `label_name`: exact member of the pinned 77-label mapping.
- `split`: `train`, `validation`, or `test`.
- Validation must detect train/validation/test ID overlap.
- Exact duplicate text across splits must be counted and reported. Removing
  upstream duplicates is not permitted without a separate documented decision.

## Baseline

### Model

An scikit-learn pipeline:

1. word TF-IDF with unigram and bigram features;
2. lowercase English text;
3. configurable maximum feature count;
4. multinomial-capable logistic regression.

### Why this baseline

- It is meaningful for short intent text.
- It is fast and CPU-friendly.
- It exposes whether the transformer adds value beyond lexical cues.
- It produces class probabilities needed for diagnostic calibration, although
  the MVP abstention threshold belongs to the transformer interface.

The baseline is not a dummy majority-class comparator.

## Improved model

### Selected checkpoint

`distilbert-base-uncased` with a 77-class sequence-classification head.

### Initial training configuration

| Parameter | Initial value | Fallback |
|---|---:|---:|
| Maximum sequence length | 96 | 64 if profiling proves sufficient |
| Epochs | 2 | 1 if Hour 8 stop condition is reached |
| Train batch size | 16 | 8 |
| Evaluation batch size | 32 | 16 |
| Learning rate | `2e-5` | no weekend search |
| Weight decay | `0.01` | unchanged |
| Mixed precision | CUDA fp16 | disabled on CPU |
| Selection metric | validation macro-F1 | unchanged |
| Seed | 42 | unchanged |

These are starting values, not claimed optimal hyperparameters. The weekend
scope permits one memory-driven batch adjustment, not a tuning study.

### Why DistilBERT

- Appropriate for English short-text classification.
- Fits the specified laptop comfortably with conservative batches.
- Provides real Hugging Face/PyTorch fine-tuning.
- Has a much smaller operational footprint than a generative LLM.
- Keeps the model question aligned with the business task.

## Threshold selection

The threshold is selected using transformer validation predictions only.

1. Calculate maximum softmax probability and correctness per validation item.
2. Enumerate candidate thresholds from sorted unique confidences plus endpoints.
3. For each threshold calculate:
   - coverage;
   - accepted count;
   - accepted accuracy;
   - selective risk (`1 - accepted accuracy`).
4. Discard thresholds below configured minimum coverage, initially `0.70`.
5. Select the remaining threshold with the lowest selective risk.
6. Break ties by higher coverage, then lower threshold.
7. Persist the selected threshold, rule, minimum coverage, validation counts,
   and validation metrics.

The `0.70` coverage floor is a demonstration policy, not a validated business
requirement. The evaluation report must show the full risk/coverage curve so an
interviewer can challenge it.

## Evaluation metrics

### Primary task metric

**Macro-F1** gives every intent equal weight and exposes weak class performance
that can be hidden by aggregate accuracy.

### Secondary classification metrics

- accuracy;
- weighted-F1;
- per-class precision, recall, F1 and support;
- confusion pairs with the largest counts.

### Confidence and abstention metrics

- expected calibration error with fixed documented bins;
- coverage;
- abstention rate;
- accepted accuracy;
- selective risk;
- risk/coverage curve.

### Latency metrics

- p50 and p95 single-request latency;
- warm-up count;
- measured request count;
- device, precision, batch size, sequence length, and software versions.

Latency is descriptive for the measured laptop, not an SLA.

### Unsupported-query fixture

Report:

- number of curated unsupported examples;
- abstained count and rate;
- examples of false acceptance by category.

The report must contain:

> This curated fixture is a behavioral check, not a representative OOD
> benchmark and not evidence of general unsupported-query detection.

## Data leakage controls

- Preserve upstream test isolation.
- Fit TF-IDF vocabulary on train only.
- Select epoch and threshold on validation only.
- Never inspect test metrics to select hyperparameters.
- Hash and compare example IDs used by baseline and transformer.
- Record test IDs in the evaluation manifest.
- Do not place curated unsupported examples in training.

## Reproducibility controls

- Seed Python, NumPy, scikit-learn and PyTorch.
- Record CUDA, cuDNN, PyTorch, Transformers and driver metadata.
- Use deterministic algorithms where practical and report when an operation
  cannot comply.
- Pin dataset and model revisions.
- Lock dependencies.
- Persist the complete training configuration.
- Save label ordering explicitly.
- Generate evaluation outputs from saved artifacts, not in-memory models.

Reproducibility means repeatable conditions and close results on the same
environment. Exact equality across releases, platforms, or GPU architectures is
not promised.

## Artifact bundle

```text
artifacts/intentguard-distilbert/<run_id>/
├── config.json
├── model/
├── tokenizer/
├── labels.json
├── threshold.json
├── provenance.json
├── validation_metrics.json
└── manifest.json
```

`manifest.json` contains hashes of the small metadata files and identifies the
model/tokenizer directories. Generated weights are not committed to Git.

## Limitations

- The domain is English consumer banking.
- Labels represent BANKING77’s taxonomy, not a real organization’s routing
  hierarchy.
- Maximum softmax confidence does not guarantee semantic correctness.
- One global threshold may behave unevenly across classes.
- The unsupported fixture is small and curated.
- Training data may not represent contemporary language, spelling, geography,
  accessibility needs, fraud scenarios, or real operational distributions.
- The model may confidently misroute adversarial, ambiguous, or novel inputs.
- No user study or business-outcome evaluation exists.

## Hardware and memory expectations

Expected planning envelope:

- model download: roughly hundreds of megabytes;
- system RAM: below 12 GB during the intended workflow;
- GPU memory: target below 6 GB with batch size 16 and sequence length 96;
- baseline: CPU, typically minutes;
- transformer fine-tuning: target under one hour on the specified GPU;
- CPU inference: supported but slower;
- CPU full fine-tuning: possible in principle but outside the weekend time box.

These are implementation budgets. The final README must replace or qualify them
with measured observations.

