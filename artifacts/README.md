# Artifact directory

Immutable, versioned model artifacts are written here. Generated weights and metadata are ignored by Git; this README is the tracked contract.

`make baseline` (U03) writes the TF-IDF logistic-regression bundle:

```text
artifacts/intentguard-baseline/<run_id>/
├── config.json       # the frozen baseline hyperparameters
├── labels.json       # the ordered canonical label map
├── provenance.json   # dataset revision, split fingerprints, dependency versions
├── manifest.json     # SHA-256 and byte size of every other file
└── model.joblib      # the fitted scikit-learn pipeline
```

`<run_id>` is derived from the dataset revision and a hash of the configuration, not from a wall-clock timestamp, so an identical run always names the same bundle. The creation timestamp is recorded inside `provenance.json`, where it cannot make the identity irreproducible. This diverges from the "timestamped directory" wording in `ARCHITECTURE.md`; the specification is unchanged and the divergence is deliberate.

A completed bundle is immutable. Saving refuses to overwrite an existing `run_id`, bundles are staged and renamed into place so an interrupted write publishes nothing, and every checksum is re-verified on load.

`make train` (U04) writes the transformer bundle on the same terms, adding `model/`, `tokenizer/`, `threshold.json`, and `validation_metrics.json` beside the shared `config.json`, `labels.json`, `provenance.json`, and `manifest.json`. Its manifest covers every nested payload file, so a tampered weight or tokenizer file fails on load. The selected threshold is chosen from validation data only, and saving refuses any threshold not sourced from validation.

Bundles are untracked, so a fresh clone contains none until `make baseline` and `make train` are run.

`make evaluate` (U05) writes no artifact. It loads both bundles read-only, re-verifies every checksum, and reads the threshold from `threshold.json`; it never fits, retrains, or mutates a bundle. Predictions are produced from the reloaded weights and tokenizer rather than from any in-memory model, so an evaluation metric is evidence about the sealed bundle itself.

Evaluation requires exactly one bundle per artifact name. If a superseded bundle from an earlier configuration is left beside the current one, `make evaluate` stops and names both instead of choosing, because a silently picked stale bundle would attribute measured metrics to a configuration nobody ran.
