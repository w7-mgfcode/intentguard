# Installation

Install the exact locked environment IntentGuard was validated with: `uv`, Make, and Python 3.11, then one command.

**Purpose:** get a fresh checkout to the point where every `make` target can run.
**Intended reader:** operators setting up a machine for the first time.

## What you'll accomplish

A working environment in which `make help` prints the command contract and `make lint` passes. Prerequisites: a POSIX shell, Git, and roughly 2 GB of free disk for the environment plus dataset cache; training later adds a bundle of roughly 257 MB.

## 1. Install the two prerequisites

- **`uv`** — the Python package manager this repository is locked with. Install per the upstream instructions (<https://docs.astral.sh/uv/>). `uv` provisions Python 3.11 itself when the system lacks it, so no separate Python install is required.
- **Make** — any recent GNU Make.

Nothing else is needed. There is no Docker path in strict MVP, no GPU requirement, and no cloud dependency.

## 2. Clone and set up

```bash
git clone https://github.com/w7-mgfcode/intentguard.git
cd intentguard
make setup
```

`make setup` runs `uv sync --locked --all-groups`: it installs exactly what `uv.lock` records — the same versions the recorded runs and CI used — and fails rather than resolving newer ones. Artifact provenance later records the installed versions of behavior-relevant packages, which is what makes "the same environment" checkable instead of assumed.

## 3. Verify the environment

```bash
make help    # prints the command contract
make lint    # Ruff, mypy strict, and the repository-foundation validator
make test    # the local test suite
```

Two outcomes of `make test` are correct, and the difference matters:

- **All collected tests pass** — you have a sealed transformer bundle under `artifacts/` (unlikely on a fresh clone).
- **22 tests skip** — expected on a fresh clone. The integration tests in `tests/integration/test_api.py` are gated on a sealed `intentguard-distilbert` bundle, which this repository deliberately does not track (the weights are roughly 257 MB and Git-ignored). They un-skip after [Training](training.md), or after pointing `INTENTGUARD_ARTIFACT_ROOT` at an existing bundle ([Configuration reference](../configuration.md)).

A skip is honest evidence of an absent artifact, not a failure to be silenced.

## 4. Optional: local environment variables

Serving and the acceptance audit read a small set of `INTENTGUARD_*` variables. `.env.example` is the tracked schema; copy what you need into your shell or a local (never committed) `.env`. All defaults are usable as-is — the service binds `127.0.0.1:8000` and logs at `INFO`. The full table, including one declared-but-currently-unread variable, is in the [Configuration reference](../configuration.md).

## Where things land

All generated outputs stay inside the checkout, under three Git-ignored roots declared in `configs/default.toml`:

| Directory | Written by | Contents |
|---|---|---|
| `data/` | `make data` | BANKING77 cache and provenance record |
| `artifacts/` | `make baseline`, `make train` | sealed model bundles |
| `reports/` | `make evaluate`, `make acceptance` | machine-readable evidence |

Only each directory's `README.md` is tracked — it is the contract for what appears there.

## Next

[Quickstart](quickstart.md) — the five-command path that proves the installation end to end.
