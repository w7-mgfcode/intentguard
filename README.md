# IntentGuard

Confidence-aware support intent classification with reproducible evaluation, selective prediction, and a typed FastAPI inference boundary.

> Foundation status: Gate A repository preparation is implemented. The data, baseline, transformer, evaluation, API, and real-artifact demo are still planned and their Make targets deliberately fail until their MUST umbrellas are delivered.

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

Available commands are documented by `make help`. The following targets are intentionally unavailable during Gate A and exit non-zero with their owner: `make data`, `make baseline`, `make train`, `make evaluate`, `make serve`, and `make demo`.

## Repository map

- `src/intentguard/`: application package.
- `configs/default.toml`: reviewed defaults and unresolved revision gates.
- `tests/`: foundation tests now; ML and API tests arrive with their umbrellas.
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
