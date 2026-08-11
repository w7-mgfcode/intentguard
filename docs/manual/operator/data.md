# Preparing data

`make data` downloads the pinned BANKING77 revision, validates it against the canonical contract, derives the validation split deterministically, and records provenance — all under U02's data contract.

**Purpose:** explain what `make data` actually checks and writes, so its outputs (and its failures) can be read precisely.
**Intended reader:** operators running the lifecycle; anyone auditing where the splits come from.

## What you'll accomplish

A populated `data/` directory whose contents are validated and fingerprinted, ready for [Training](training.md). Prerequisites: [Installation](installation.md); network access on the first run only.

```bash
make data
```

## The pin

The dataset is `PolyAI/banking77` at revision `1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8` — declared in `configs/default.toml` and cross-checked in code, so an edited TOML that names any other id or revision is refused at load rather than quietly honored ([Configuration reference](../configuration.md)). The same pinning discipline applies to the base model used later by `make train`.

`make data` needs network access only when a matching local cache is absent. Re-runs against a warm cache are offline and deterministic.

## What is derived, and from what

The pinned source ships two splits: 10,003 training and 3,080 test examples. IntentGuard derives its three canonical splits as:

| Split | Size | Derivation |
|---|---|---|
| train | 8,502 | source train minus the validation carve-out |
| validation | 1,501 | 15% of source train (`validation_fraction = 0.15`), seed 42, deterministic |
| test | 3,080 | the source test split, untouched |

Two properties are load-bearing:

- **Validation comes from source train only.** The test split contributes nothing to validation, so the threshold later selected on validation predictions (AC-005) cannot have seen test data even indirectly.
- **Every split is fingerprinted.** A deterministic fingerprint per split, plus a hash of the ordered 77-label map, is recorded in provenance and later sealed into every artifact bundle. `make evaluate` refuses to compare artifacts whose fingerprints disagree — the mechanism that makes "both models saw the same data" a checked fact rather than an assumption ([Evaluation](evaluation.md)).

## Validation performed

Beyond the pin, preparation validates the label contract (exactly 77 labels, matching the canonical BANKING77 names in their canonical order) and the structure of every example, and computes duplicate-text statistics across splits. A dataset that fails any check stops the run; there is no degraded continue.

## What lands on disk

`data/` is Git-ignored except for its tracked contract, [data/README.md](../../../data/README.md). `make data` writes the local dataset cache and a deterministic provenance record — dataset id, revision, split sizes and fingerprints, label-map hash, and seed — which is what later stages compare against. Deleting `data/` is always recoverable: re-run `make data`.

## Next

[Training](training.md) — both models, and the threshold that gets sealed with the transformer.
