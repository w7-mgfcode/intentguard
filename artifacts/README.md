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

U04 will write the transformer artifact and its selected threshold here on the same terms. No transformer artifact or selected threshold exists yet.
