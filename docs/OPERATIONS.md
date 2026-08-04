# Operations

## Authoritative operating contract

The complete IntentGuard specification under [`docs/specification/`](specification/README.md) is authoritative. This document is only a concise operating guide and does not replace that source.

Use the authoritative [implementation command plan](specification/docs/IMPLEMENTATION_PLAN.md) for command ownership and expected evidence, and the authoritative [architecture](specification/docs/ARCHITECTURE.md) for component boundaries and data flow.

## Current local commands

```bash
make setup
make help
make data
make baseline
make train
make evaluate
make lint
make test
```

`make setup` installs the exact environment represented by `uv.lock`. `make data`
loads the pinned BANKING77 revision, writes ignored local provenance, and needs
network access only when a matching local cache is absent. `make baseline` trains,
reloads, and measures the lexical baseline. `make train` fine-tunes DistilBERT on
CPU, selects the abstention threshold from validation predictions only, and seals one
immutable bundle; when a bundle whose content-derived run ID already exists is found,
it reuses that bundle and rebuilds only the report instead of retraining. `make evaluate`
loads both sealed bundles, reads the persisted threshold, and measures both models on the
untouched test split. `make lint` runs Ruff, mypy, and the repository-foundation
validator. `make test` runs the local tests.

`make evaluate` requires exactly one bundle under each of
`artifacts/intentguard-baseline/` and `artifacts/intentguard-distilbert/`. If a
superseded bundle is left beside a current one the run stops and names both rather
than guessing, because attributing metrics to the wrong configuration is worse than
failing. Remove the superseded bundle before rerunning.

Before predicting anything, `make evaluate` proves the two bundles agree with each
other and with the locally prepared splits on dataset id, dataset revision, label-map
hash, all three split fingerprints, and the hash of the evaluated test example IDs. A
disagreement is a hard failure: comparing two models trained on different data would
produce a number that looks like a comparison but is not one.

## Repository lifecycle validation

Select the Git-state expectation explicitly at approval boundaries:

```bash
# Gate A
uv run python scripts/validate_foundation.py \
  --expect-git-state uninitialized

# Gate B before remote creation
uv run python scripts/validate_foundation.py \
  --expect-git-state local-only

# Routine lint uses the lifecycle-neutral default: --expect-git-state any
make lint
```

All modes run the same repository-content checks and inspect Git read-only. The `local-only` mode requires `main` with no remote or upstream, but it permits the pre-commit state immediately after `git init`.

## Remaining command lifecycle

The remaining intended local lifecycle is:

```bash
make serve
make demo
```

`make serve` and `make demo` currently exit non-zero and name their owning umbrella
(U06). They must not be used as evidence of API completion.

`make evaluate` succeeds, but U05 is **Partial**: the curated unsupported-request
fixture is not part of the report yet. A successful `make evaluate` is therefore not
evidence that U05 is complete.

`make evaluate` now also measures single-request latency, which accounts for most of
its roughly 30-second runtime and is the only output that differs between two runs of
the same configuration. Two consecutive runs producing the same `run_id` and the same
directory but different p50 values is the intended behaviour, not a defect: the run ID
covers the sampling protocol and never the measured durations. Everything else in
`comparison.json` is byte-identical across runs.

The threshold lifecycle is fixed: `make train` chooses it from validation predictions and persists it in the immutable transformer artifact; `make evaluate` loads that value and applies it to test predictions without tuning on test labels. `scripts/evaluate.py` imports neither `select_threshold` nor any fitting function, so re-deriving a threshold from test data is not something that code path can express; a test enforces this by inspecting the script's syntax tree rather than trusting a text search.

## Configuration and generated outputs

Reviewed defaults live in `configs/default.toml`. The dataset revision is pinned
by U02 and the base-model revision is pinned by U04; no unresolved revision gate
remains. Local settings may be supplied through variables shown in `.env.example`;
do not commit `.env` files.

Generated data, artifacts, and reports stay under their named root directories and are untracked except for README contracts. Serving must eventually load an already-created artifact; it must never train or mutate that artifact.

## CPU and GPU claims

GitHub Actions is CPU-only. No CUDA, GPU speed, or GPU compatibility claim is valid until separately executed and recorded. Docker is POST-WEEKEND and is not an operating path for strict MVP.
