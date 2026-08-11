# CI integration

Running IntentGuard's gates on a clean runner: what the shipped workflow does, why the acceptance audit runs degraded there, and how to read a CI result without over-trusting a green badge.

**Purpose:** reproduce the repository's CI discipline in your own pipeline, and interpret its outcomes correctly.
**Intended reader:** integrators wiring IntentGuard into CI; reviewers auditing a run.

## What you'll accomplish

A CI job equivalent to the shipped one, plus the vocabulary to explain each expected skip and degraded row. Prerequisite: the [Quickstart](../operator/quickstart.md) gates run locally.

## The shipped workflow

One workflow, `.github/workflows/ci.yml` ("CPU validation"): an `ubuntu-latest` job with a 20-minute timeout that pins `uv` and Python, then runs the same four targets an operator runs:

```
make setup   →   make lint   →   make test   →   make acceptance
```

CI is **CPU-only, intentionally**. No CUDA, GPU speed, or GPU compatibility claim is valid anywhere in the repository until separately executed and recorded — the workflow is part of that discipline, not a cost compromise to apologise for.

## Why a clean runner behaves differently

A clean runner has neither a sealed bundle (roughly 257 MB, deliberately untracked) nor a Hugging Face cache. Two documented consequences:

**Test skips.** Of the current 650 collected tests, a clean runner skips 39: the 22 in `tests/integration/test_api.py` gated on a sealed `intentguard-distilbert` bundle, plus 17 in `tests/integration/test_training_smoke.py` gated on the cached base model. The recorded clean-runner result is 611 passed / 39 skipped. A skip here is honest evidence of an absent artifact — a CI job that trained a bundle to un-skip them would produce a *different* threshold and artifact, making the evidence a statement about the runner, and would not fit the timeout ([LIMITATIONS.md](../../LIMITATIONS.md)).

**A degraded acceptance audit.** Without evidence roots, `make acceptance` still exercises the full ownership contract and verdict rules; artifact-backed rows are recorded as `not_evidenced` with reasons, reported as *environmental gaps* separately from verdict causes. A degraded run and a fully-evidenced run reach the same cause list — that property is what makes the CI invocation meaningful rather than ceremonial. The recorded runs: fully evidenced 43 passed / 1 not evidenced; degraded 23 passed / 21 not evidenced with 14 environmental gaps; both verdict `PASS`, exit 0.

## Pointing the audit at real evidence

To audit against artifacts produced elsewhere (another worktree, a build stage that ran `make train`):

```bash
INTENTGUARD_ARTIFACT_ROOT=/path/to/artifacts \
INTENTGUARD_REPORT_ROOT=/path/to/reports \
  uv run python scripts/validate_acceptance.py --print-only
```

When the artifact root is redirected and the report root is not, the report root defaults to `<artifact root>/../reports`, so one run's evidence is never silently mixed with another's. **Prefer `--print-only` when auditing evidence you did not produce in this worktree** — a default run writes `reports/acceptance.json` into the repository it runs in, and writing beside somebody else's preserved records is the failure the flag exists to prevent. When you do want the file, direct it explicitly with `--output` into your own ignored `reports/`.

## Reading a CI result honestly

Three rules, each learned the measured way (the receipts are in [LIMITATIONS.md](../../LIMITATIONS.md) and the U07 row of [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md)):

1. **A failing audit must fail the job.** The acceptance step once carried `continue-on-error: true`, and the audit's truthful `FAIL` verdicts were masked behind green workflow conclusions. That masking has been removed; keeping the pattern out of your own pipeline is the single most important porting decision.
2. **Quote the layer you ran.** `scripts/validate_acceptance.py` exits 1 on a `FAIL` verdict; `make` then reports `Error 1` and itself exits 2. A CI log ends with exit code 2 for the same event the script reports as 1.
3. **Read the step logs, not the conclusion.** A conclusion can misreport in either direction: recorded runs printed `FAIL` with causes under a green conclusion (the masking era), and one run attempt reported `failure` having executed nothing at all — no runner acquired, zero steps — an infrastructure non-result, not evidence about the tree. The current `PASS` in the status document is CI-corroborated because the logs of the confirming run were read, not because a badge was green.

## Porting checklist

- [ ] Pin the toolchain (`uv`, Python 3.11) and install with `make setup` (locked, never resolving).
- [ ] Run `make lint`, `make test`, `make acceptance` as separate, individually failing steps.
- [ ] No `continue-on-error` on any gate.
- [ ] Expect and document the 39 clean-runner skips; treat a *changed* skip count as a finding.
- [ ] If a stage supplies real artifacts, pass both evidence roots and prefer `--print-only`.
- [ ] Budget for the 20-minute CPU timeout; training does not fit inside it, by design.

## Next

Shared references: [Configuration](../configuration.md) · [Troubleshooting](../troubleshooting.md) · [FAQ](../faq.md) · [Glossary](../glossary.md).
