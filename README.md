# IntentGuard

Confidence-aware support intent classification with reproducible evaluation, selective prediction, and a typed FastAPI inference boundary.

> The foundation, BANKING77 data contract, TF-IDF baseline, and DistilBERT training path are implemented. Comparative test evaluation runs and is measured, now including calibration, risk/coverage curves, and single-request latency, but remains partial: the curated unsupported-request fixture is outstanding. The API and the real-artifact demo remain planned, and their Make targets deliberately fail until their MUST umbrellas are delivered.
>
> **Measured result:** on the held-out test split the TF-IDF baseline reaches macro-F1 0.8654 and the fine-tuned DistilBERT reaches 0.6620. The baseline wins by 0.2034. Reporting that honestly is what AC-004 asks for; nothing was retuned after the number was seen.
>
> **Measured caveat:** neither model is well calibrated. Both are underconfident — baseline ECE 0.4883, transformer ECE 0.4697 — so a confidence score is a ranking signal for abstention, not a probability of correctness. Single-request latency on one measured CPU is 0.53 ms p50 for the baseline and 10.68 ms p50 for the transformer; that is descriptive for that machine, not a service level.

## What this repository is for

IntentGuard is a compact portfolio project built around BANKING77. Its strict Weekend MVP will compare a TF-IDF logistic-regression baseline with one fine-tuned DistilBERT classifier, select an abstention threshold from validation data, evaluate once on held-out test data, and serve the immutable transformer artifact through FastAPI.

The authoritative design is [docs/specification/README.md](docs/specification/README.md). Local GitHub backlog material is indexed at [docs/backlog/README.md](docs/backlog/README.md). Neither this README nor the backlog replaces the specification.

## Foundation quick start

Prerequisites: `uv` and Make. The project requires Python 3.11; `uv` manages that interpreter when needed.

```bash
make setup
make lint
make test
```

Available commands are documented by `make help`. `make data`, `make baseline`,
`make train`, and `make evaluate` are operational: they prepare the pinned BANKING77
contract, measure the lexical baseline, fine-tune DistilBERT on CPU, and compare both
sealed artifacts on the untouched test split. The following targets are intentionally
unavailable and exit non-zero with their owner: `make serve` and `make demo`.

## Repository map

- `src/intentguard/`: application package.
- `configs/default.toml`: reviewed defaults, including the pinned dataset and base-model revisions.
- `tests/`: foundation, data, baseline, transformer, and evaluation tests; API tests arrive with their umbrella.
- `data/`, `artifacts/`, `reports/`: generated local outputs; only their README files are tracked.
- `docs/specification/`: sole authoritative specification.
- `docs/backlog/`: local issue bodies, traceability, Project design, and execution manifests.
- `docs/OPERATIONS.md`: current command and operating guidance.
- `docs/IMPLEMENTATION_STATUS.md`: honest capability status.
- `docs/LIMITATIONS.md`: current limitations and unverified claims.

## Scope controls

Docker is POST-WEEKEND. There is no frontend, database, cloud deployment, experiment tracker, monitoring stack, or additional model family in strict MVP. The strict demonstration must load the real transformer artifact; deterministic prediction is limited to tests or explicitly degraded mode.

## License

IntentGuard source code is available under the [MIT License](LICENSE). Dataset and model artifacts retain their upstream licenses and are not covered by this repository's code license.
