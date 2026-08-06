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
make serve
make demo
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
untouched test split. `make serve` loads one sealed bundle and serves it over HTTP.
`make demo` starts that same service and exercises it over a real socket. `make lint`
runs Ruff, mypy, and the repository-foundation validator. `make test` runs the local
tests.

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

## Serving and the strict demonstration

`make serve` and `make demo` are wired to the real sealed artifact. Both reach
`python -m intentguard.app`: `make serve` invokes it directly, and `make demo` runs
`scripts/demo.py`, which starts that same entry point as a child process. The demo
therefore exercises the shipped serving path rather than a private one.

```bash
# Serve the bundle found under the configured artifact root
make serve

# Start the same service, then prove one accept and one abstain over HTTP
make demo
```

`/v1/predict` is a synchronous handler on purpose, so its blocking forward pass runs
in the threadpool rather than on the event loop. Measured locally with 16 concurrent
predictions in flight, `/health` answered in 17 ms; the same check against a coroutine
handler answered in 96 ms, because every request had to wait its turn on the loop.
Both figures are single observations on one CPU machine, not a service-level claim.

Both commands require an existing transformer bundle and neither can create one:
serving loads the persisted threshold and has no code path that fits a model,
selects a threshold, or writes to the artifact. If the bundle is absent or fails a
checksum, startup raises *before* the port is bound, so a process that is listening
is a process whose artifact was verified.

Point either command at a bundle outside the default root with
`INTENTGUARD_ARTIFACT_ROOT`. `INTENTGUARD_HOST` (default `127.0.0.1`),
`INTENTGUARD_PORT` (default `8000`), and `INTENTGUARD_LOG_LEVEL` (default `INFO`)
control the listener. The default host is loopback deliberately: the service is
unauthenticated, so binding every interface is opt-in rather than the default.

`INTENTGUARD_LOG_LEVEL` accepts `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`,
case-insensitively — the intersection of what the service logger and Uvicorn each
understand, not the union. `NOTSET`, `WARN`, and `FATAL` are refused although Python's
`logging` resolves them, and `TRACE` is refused although Uvicorn accepts it. All four
are rejected while resolving settings, so an unusable value fails in under a second
instead of after a 265 MB bundle has been loaded and re-hashed. Every rejection names
the variable and the accepted set.

`make demo` sends two requests: one in-domain, and the curated unsupported row
`unsupported-001`, whose abstention was measured in the E05 evaluation. It reports
the confidences it observed but asserts only the two decisions — pinning a
confidence would convert a measurement into a fixture. It chooses its own ephemeral
port so a `make serve` already running is not disturbed, and terminates the child in
a `finally` block, escalating to `kill`, so no process outlives the target. If
either decision does not hold the demo exits non-zero; that is a real observation
about the loaded artifact and must not be resolved by changing the model or the
threshold.

## Evaluation and the threshold lifecycle

`make evaluate` succeeds and U05 is **Implemented**: the test-split comparison,
calibration, risk/coverage curves, latency, and the curated unsupported-request check
are all written. It fails loudly rather than degrading if the curated fixture is
missing, malformed, or collides with any BANKING77 split — a fixture row that exists
in training data would make its abstention a measure of memorisation, so that is an
authoring error to fix and not something the run works around.

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

Generated data, artifacts, and reports stay under their named root directories and are untracked except for README contracts. Serving loads an already-created artifact and never trains or mutates it.

## CPU and GPU claims

GitHub Actions is CPU-only. No CUDA, GPU speed, or GPU compatibility claim is valid until separately executed and recorded. Docker is POST-WEEKEND and is not an operating path for strict MVP.
