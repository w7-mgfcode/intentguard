# Operations

## Authoritative operating contract

The complete IntentGuard specification under [`docs/specification/`](specification/README.md) is authoritative. This document is only a concise operating guide and does not replace that source.

Use the authoritative [implementation command plan](specification/docs/IMPLEMENTATION_PLAN.md) for command ownership and expected evidence, and the authoritative [architecture](specification/docs/ARCHITECTURE.md) for component boundaries and data flow.

## Current local commands

```bash
make setup
make help
make data
make lint
make test
```

`make setup` installs the exact environment represented by `uv.lock`. `make data`
loads the pinned BANKING77 revision, writes ignored local provenance, and needs
network access only when a matching local cache is absent. `make lint` runs Ruff,
mypy, and the repository-foundation validator. `make test` runs the local tests.

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

## Planned command lifecycle

The remaining intended local lifecycle is:

```bash
make baseline
make train
make evaluate
make serve
make demo
```

`make baseline` through `make demo` currently exit non-zero and name their owning
umbrella. They must not be used as evidence of ML or API completion.

The threshold lifecycle is fixed: `make train` chooses it from validation predictions and persists it in the immutable transformer artifact; `make evaluate` loads that value and applies it to test predictions without tuning on test labels.

## Configuration and generated outputs

Reviewed defaults live in `configs/default.toml`. The dataset revision is pinned
by U02; the model revision remains explicitly unresolved until U04. Local
settings may be supplied through variables shown in `.env.example`; do not
commit `.env` files.

Generated data, artifacts, and reports stay under their named root directories and are untracked except for README contracts. Serving must eventually load an already-created artifact; it must never train or mutate that artifact.

## CPU and GPU claims

GitHub Actions is CPU-only. No CUDA, GPU speed, or GPU compatibility claim is valid until separately executed and recorded. Docker is POST-WEEKEND and is not an operating path for strict MVP.
