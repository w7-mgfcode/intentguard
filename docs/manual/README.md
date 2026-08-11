# User manual

The complete operating and integration manual for IntentGuard: how to install, train, evaluate, and serve the system, and how to build against its API and artifacts.

**Purpose:** one navigable place that takes a reader from an empty checkout to a running, verified service — and explains every number the system reports.
**Intended reader:** anyone running IntentGuard for the first time, and anyone integrating against its HTTP API or artifact bundles.

This manual documents behavior; it does not define it. The authoritative design lives in [the specification](../specification/README.md), the current capability status in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md), and what the measured numbers do *not* support in [LIMITATIONS.md](../LIMITATIONS.md). Where this manual and the specification disagree, the specification wins — and the disagreement is a bug in this manual.

## Two tracks

**Operator track** — you want to run IntentGuard: reproduce the data, train both models, evaluate them, and serve the sealed artifact.

1. [What IntentGuard is](operator/concepts.md) — the concepts: intent classification, confidence, abstention, sealed artifacts, strict MVP.
2. [Installation](operator/installation.md) — prerequisites and `make setup`.
3. [Quickstart](operator/quickstart.md) — the five-command review path.
4. [Preparing data](operator/data.md) — `make data` and the pinned BANKING77 contract.
5. [Training](operator/training.md) — `make baseline`, `make train`, and how the threshold is selected.
6. [Evaluation](operator/evaluation.md) — `make evaluate` and the provenance checks behind a valid comparison.
7. [Serving](operator/serving.md) — `make serve`, `make demo`, and what startup verifies.
8. [Interpreting results](operator/interpreting-results.md) — what every reported metric means, and what it does not.

**Integrator track** — you want to build on IntentGuard: call its API, read its artifacts, or extend it.

1. [API reference](integrator/api-reference.md) — both endpoints, every error shape, and worked requests.
2. [Code architecture](integrator/code-architecture.md) — a module-by-module tour of `src/intentguard/`.
3. [Artifact format](integrator/artifact-format.md) — the sealed bundle layout, manifest, and checksum contract.
4. [Extending IntentGuard](integrator/extending.md) — what may change, what must not, and why.
5. [CI integration](integrator/ci-integration.md) — running the gates on a clean runner, and degraded-mode semantics.

**Shared references** — used by both tracks:

- [Configuration reference](configuration.md) — every `configs/default.toml` field and every `INTENTGUARD_*` environment variable.
- [Troubleshooting](troubleshooting.md) — symptom → cause → fix.
- [FAQ](faq.md)
- [Glossary](glossary.md) — the product vocabulary, used consistently across this manual.

## Prerequisites, once

Everything in this manual assumes: `uv` and Make installed, Python 3.11 (provisioned by `uv` when absent), a CPU machine. No GPU is used anywhere — training, evaluation, and serving are CPU-only by decision, and no CUDA claim is evidenced in this repository.

## How this manual reports numbers

Every metric quoted here comes from a tracked document ([README.md](../../README.md), [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md)) or a generated report you can reproduce (`make evaluate`). The headline result is that **the TF-IDF baseline beats the fine-tuned DistilBERT** by 0.2034 macro-F1 — reported as measured, not retuned away. Numbers this manual could not verify against the source are marked as unverified rather than stated as fact.
