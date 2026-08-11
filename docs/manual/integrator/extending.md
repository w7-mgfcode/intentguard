# Extending IntentGuard

What an integrator may change safely, what the repository's controls will actively refuse, and where the specified scope boundary lies.

**Purpose:** channel changes through the paths the design supports, before a refused load or a failed gate does it the hard way.
**Intended reader:** integrators adapting the system; contributors. The scope authority is [SCOPE_CONTROL.md](../../specification/docs/SCOPE_CONTROL.md); the change-management rules live in the repository's `AGENTS.md`.

## What you'll accomplish

For the most common modifications, know: the sanctioned mechanism, the controls you will meet, and the honesty obligations that travel with the change.

## The safe path for any behavioral change

1. Change configuration or code on a branch — never a sealed bundle.
2. Re-run the affected lifecycle stages (`make data` → `baseline`/`train` → `evaluate`); a config change produces a **new** run ID and a sibling bundle by design.
3. Remove the superseded bundle deliberately — [Evaluation](../operator/evaluation.md) refuses to run beside a stale sibling.
4. Re-run the gates: `make lint`, `make test`, `make acceptance`.
5. Update [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md) honestly — a capability whose evidence changed is re-stated with its new evidence, and a degraded path is marked as degraded, not `Implemented`.

## Retraining with a different configuration

Edit the `[baseline]`, `[training]`, or `[threshold]` blocks of `configs/default.toml` within their validated ranges ([Configuration reference](../configuration.md)). Constraints you will meet:

- **Allow-listed choices are closed sets.** `solver` ∈ {`lbfgs`, `saga`}, `class_weight` ∈ {`balanced`, `none`}, `threshold_source` = `validation`, `threshold.objective` = `selective_risk`, `selection_metric` = `validation_macro_f1`. Adding a new value means changing the allow-list in `config.py` — a reviewed code change, not a config edit — because each list is the boundary of what the evidence and the leakage argument cover.
- **The pins are cross-checked in code.** `dataset_id`, `dataset_revision`, `base_model_id`, and `base_model_revision` in the TOML must equal the constants in `config.py`. Repointing the dataset or base model is a two-place change, deliberately: the pin is a contract (U02/U04), not a default.
- **Numbers are range-validated** (positive integers, finite floats, fractions in their intervals — including the NaN/inf traps), so a typo fails at load with a named field.

After the retrain, the measured-results story changes with it: previously recorded metrics describe the previous configuration. Do not carry them forward — re-measure with `make evaluate` and quote the new report.

## Changing the abstention policy

The threshold *value* is never edited — it is selected and sealed ([Training](../operator/training.md)). The legitimate knob is `[threshold] minimum_coverage`: raising it trades coverage floor against selective risk at selection time. The selection rule itself (`min_selective_risk_at_min_coverage`, version 1) is versioned; a different rule is a new version with its own evidence, not a silent redefinition. A hand-edited `threshold.json` fails the bundle's checksum manifest before its content is even considered — and a re-sealed bundle claiming a non-`validation` source is refused at load twice (artifact layer, serving boundary).

## Adding to the unsupported-request fixture

`tests/fixtures/unsupported_requests.jsonl` — one JSON object per line: `request_id`, `text`, `category`, `rationale`. Two hard rules: the category must be one of the six declared ones (a new category is a code change, so a typo cannot mint a category with a count of one), and **no fixture text may appear in any BANKING77 split** — a colliding row measures memorisation, not abstention, and `make evaluate` fails loudly on it. Keep the framing honest: the fixture is a behavioral check, and no fixture you author can turn it into an OOD benchmark ([Interpreting results](../operator/interpreting-results.md)).

## Consuming artifacts from other tooling

Read bundles through the documented [artifact format](artifact-format.md) — verify the manifest before trusting a file, and treat `run_id` as an opaque identity. Nothing prevents an external consumer from loading the payload directly, but a consumer that skips checksum verification inherits exactly the risks the format exists to close.

## Serving changes

The API models in `schemas.py` encode the published contract, and the OpenAPI document is generated from them. A field addition is a contract change: update [INTERFACE_CONTRACT.md](../../specification/docs/INTERFACE_CONTRACT.md) (the authority), the models, and the contract tests together. Two invariants to preserve: errors keep the single envelope with fixed messages (no input echo — NFR-005 depends on it), and the `intent`↔`decision` coupling stays validated on the response.

## What is out of scope, by declaration

Strict MVP deliberately excludes: Docker (POST-WEEKEND), any frontend, database, cloud deployment, experiment tracker, monitoring stack, GPU execution (decision D10 — no CUDA claim is evidenced anywhere), authentication, and additional model families. These are not gaps awaiting a contributor; they are the scope boundary the specification draws. Extending past it is a specification change first, a code change second.

## The one rule that governs all of the above

Every change must keep the evidence story true. If your change invalidates a measured claim, the claim moves — to re-measured, or to `Partial`/`Planned` — rather than the old number surviving beside new code. The gates (`make lint`, `make test`, `make acceptance`) automate most of that discipline; [CI integration](ci-integration.md) shows how to keep them running.

## Next

[CI integration](ci-integration.md) — the gates on a clean runner.
