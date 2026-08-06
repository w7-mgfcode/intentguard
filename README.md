# IntentGuard

Confidence-aware support intent classification on BANKING77: one lexical baseline, one fine-tuned DistilBERT, reproducible evaluation on an untouched test split, abstention driven by a validation-selected threshold, and a typed FastAPI boundary that serves one sealed artifact.

**Intended use.** A compact portfolio project, built to show an honest ML lifecycle end to end. It is not a production service: there is no authentication, no horizontal scaling story, and no operational monitoring. Every number below comes from a generated report, and the headline result is that **the fine-tuned transformer loses to the lexical baseline** — reported as measured rather than retuned away.

## Review in five minutes

Prerequisites: `uv` and Make. Python 3.11 is required; `uv` provisions it when needed. Prerequisite installation is excluded from the five minutes.

```bash
make setup      # install the exact locked environment
make lint       # Ruff, mypy strict, and the repository-foundation validator
make test       # the local test suite
make demo       # start the real service and prove one accept and one abstain
make acceptance # audit every MUST identifier and print the strict-MVP verdict
```

`make demo` and `make serve` load a **sealed transformer bundle that this repository does not track** — model weights are roughly 257 MB and are ignored by Git. They read the bundle from `artifacts/` by default; point them elsewhere with `INTENTGUARD_ARTIFACT_ROOT`. If no bundle exists, create one with `make train`, or see [docs/OPERATIONS.md](docs/OPERATIONS.md) for the artifact-root variables. Both commands fail before binding a port when the bundle is missing or fails a checksum, so a listening process is one whose artifact was verified.

Then read, in order: [measured results](#measured-results) below, [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) for what is implemented and measured, and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for what these numbers do not support.

## What it does, in lifecycle order

1. **Pinned data** — BANKING77 at revision `1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`, with canonical splits and recorded local provenance.
2. **Two models** — a TF-IDF logistic-regression baseline, and one fine-tuned `distilbert-base-uncased` at revision `12040accade4e8a0f71eabdb258fecc2e7e948be`.
3. **A validation-only threshold** — `make train` selects the abstention threshold from validation predictions and seals it inside an immutable artifact. Test labels never influence it.
4. **Evaluation on the untouched test split** — `make evaluate` loads both sealed bundles, applies the persisted threshold without reselecting it, and writes machine-readable evidence.
5. **Serving** — `make serve` loads that same sealed artifact behind typed `/health` and `/v1/predict` endpoints. It has no code path that trains, fits, or rewrites an artifact.

The threshold is the spine of that sequence: selected once from validation data, sealed, then loaded unchanged by evaluation and by serving alike.

## Measured results

From evaluation run `intentguard-evaluation-1fb62b1bb463-55796a53ca3e` on the 3,080-example test split, both models measured from their reloaded artifacts at the persisted threshold `0.16841767053420467`. Report contents are described in [reports/README.md](reports/README.md); the reports themselves are generated and untracked, so reproduce them with `make evaluate` or read the run that your own copy writes.

| Metric | TF-IDF baseline | DistilBERT |
|---|---|---|
| Accuracy | 0.8653 | 0.6955 |
| Macro-F1 | 0.8654 | 0.6620 |
| Coverage at threshold | 0.7500 | 0.6799 |
| Accepted accuracy | 0.9333 | 0.8161 |
| Selective risk | 0.0667 | 0.1839 |
| Expected calibration error | 0.4883 | 0.4697 |

**The baseline wins by 0.2034 macro-F1**, and the comparison verdict recorded in the report is `baseline_better`. Nothing was retuned after that number was seen — changing a configuration, seed, or threshold in response to a test metric would breach the leakage controls, so the result stands as measured. It reflects the frozen configuration in `configs/default.toml` (two CPU epochs, learning rate 2e-5) and is not a statement about DistilBERT's ceiling on BANKING77.

## What confidence does and does not mean

**A confidence score here is a ranking signal for abstention, not a probability of correctness.** Both models are substantially underconfident: the baseline's mean confidence is 0.3770 against an accuracy of 0.8653, and the transformer's is 0.2258 against 0.6955. No recalibration was applied. Abstention still works, because it only needs confidences to rank; the cost underconfidence imposes is coverage — answers the model would have got right are discarded.

The transformer's confidence never exceeded 0.6000 on any test example, so read the threshold `0.1684` relative to that observed range rather than as an absolute probability.

**The curated unsupported-request check is a behavioral check, not an out-of-distribution benchmark.** All 12 hand-written requests, spanning six declared categories, abstained at the persisted threshold. That is a passed check and not evidence of general unsupported-query detection — an abstention rate over a fixture its author chose is partly a statement about that author's imagination. It is meaningful only beside the in-distribution contrast: mean confidence 0.0503 on the fixture against 0.2258 on the test split, where 0.3201 of test examples also abstain. A total rate alone would be indistinguishable from a model that abstains on everything. No accuracy is reported for the fixture, because no BANKING77 intent is correct for any of its rows.

Single-request latency, measured on one CPU machine at batch size 1 over 200 real test texts after 20 discarded warm-up requests: the baseline's p50 sits near 0.55 ms, the transformer's between roughly 8.6 ms and 10.7 ms. **Descriptive for that machine, not a service level**, and quoted as a range deliberately — latency is the one part of the evaluation report that does not reproduce between runs of the same configuration. Quote exact figures only from a report you have in hand. No GPU or CUDA claim is evidenced anywhere; CI is intentionally CPU-only.

## Strict-MVP status

Strict MVP requires every MUST capability to be `Implemented` and every applicable claim to be `Measured`. `make acceptance` audits all 42 primary identifiers and prints an enumerated verdict; it is the authority on that question, not this sentence.

The current verdict and each capability's evidence live in [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md). Where a claim is measured locally but not in CI, that document and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) say so explicitly rather than letting a green badge imply otherwise.

## Repository map

- `src/intentguard/`: application package — data, baseline, training, threshold, evaluation, API, and predictor.
- `configs/default.toml`: reviewed defaults, including the pinned dataset and base-model revisions.
- `scripts/`: the command entry points behind each Make target, plus the foundation and acceptance validators.
- `tests/`: unit, contract, and integration suites.
- `data/`, `artifacts/`, `reports/`: generated local outputs; only their README files are tracked.
- `docs/specification/`: the sole authoritative specification.
- `docs/backlog/`: local issue bodies, traceability, and Project design.
- [docs/OPERATIONS.md](docs/OPERATIONS.md): commands, configuration, artifact paths, and troubleshooting.
- [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md): capability status, evidence, and the strict-MVP verdict.
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md): limitations and unverified claims.

The authoritative design is [docs/specification/README.md](docs/specification/README.md), and local backlog material is indexed at [docs/backlog/README.md](docs/backlog/README.md). Neither this README nor the backlog replaces the specification.

## Scope controls

Docker is POST-WEEKEND. There is no frontend, database, cloud deployment, experiment tracker, monitoring stack, or additional model family in strict MVP. The strict demonstration must load the real transformer artifact; deterministic prediction is confined to tests and to an explicitly labelled degraded mode.

## Attribution and license

IntentGuard source code is available under the [MIT License](LICENSE). Dataset and model artifacts retain their upstream licenses and are not covered by this repository's code license: BANKING77 is published by PolyAI as `PolyAI/banking77`, and the base model is `distilbert/distilbert-base-uncased`. Both are pinned by revision in `configs/default.toml`, and neither is redistributed here.
