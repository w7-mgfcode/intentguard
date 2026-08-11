# Quickstart

The five-command review path: prove the environment, the gates, the live service, and the acceptance verdict — in about five minutes on a warm environment.

**Purpose:** the shortest honest end-to-end exercise of the system.
**Intended reader:** operators who finished [Installation](installation.md); reviewers following the README's "Review in five minutes".

## What you'll accomplish

Each command below is a gate, and each gate's pass condition is stated so you know what you actually proved. The sequence mirrors the README exactly.

```bash
make setup      # install the exact locked environment
make lint       # Ruff, mypy strict, and the repository-foundation validator
make test       # the local test suite
make demo       # start the real service and prove one accept and one abstain
make acceptance # audit every MUST identifier and print the strict-MVP verdict
```

## What each command proves

**`make setup`** — the locked environment resolves and installs. Near-instant when already synced.

**`make lint`** — three checks in sequence: Ruff (style and correctness lints), mypy in strict mode over `src`, `scripts`, and `tests`, and `scripts/validate_foundation.py`, which asserts the repository-foundation contract (10 checks: configuration validity, pinned revisions, directory contracts, and Git state). All three must exit 0.

**`make test`** — the pytest suite. On a tree with no sealed bundle, expect skips (22 tests gated on the artifact; see [Installation](installation.md)); skips are correct there, failures are not.

**`make demo`** — the strict real-artifact demonstration, and the step with a real precondition: **it needs a sealed transformer bundle**. If `artifacts/intentguard-distilbert/` is empty, the demo fails before binding a port. Two ways to satisfy it:

- train one locally: `make data && make baseline && make train` (see [Training](training.md) for what to expect), or
- point at an existing bundle: `INTENTGUARD_ARTIFACT_ROOT=/path/to/artifacts make demo`.

What the demo then does ([Serving](serving.md) has the full anatomy): starts `python -m intentguard.app` as a child process on an ephemeral port, waits for `/health` to report ready, sends one in-domain request (expected `accept`) and the curated unsupported row `unsupported-001` (expected `abstain`), prints the transcript, and terminates the child. It asserts only the two decisions — never a confidence value, because pinning one would convert a measurement into a fixture. A demo that exits non-zero is a real observation about the loaded artifact; do not resolve it by changing the model or the threshold.

**`make acceptance`** — runs `scripts/validate_acceptance.py`, which classifies all 42 primary T/FR/NFR/AC identifiers against the evidence it can reach and prints an enumerated strict-MVP verdict. Without evidence roots it runs **degraded**: artifact-backed rows report `not_evidenced` with reasons, separated from real verdict causes — the verdict remains comparable to a fully-evidenced run. A non-zero exit is the gate speaking, not a broken command. Details in [CI integration](../integrator/ci-integration.md).

## Reading the outcome

- All five exit 0 → your checkout reproduces the repository's own promises.
- `make demo` failed for want of a bundle → expected on a fresh clone; train or point at a bundle, re-run.
- `make acceptance` printed causes → read them; each names an identifier and its evidence gap. [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md) carries the current expected verdict (**PASS**).

## Next

The full lifecycle, in order: [Preparing data](data.md) → [Training](training.md) → [Evaluation](evaluation.md) → [Serving](serving.md).
