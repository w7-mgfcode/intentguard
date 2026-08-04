# Report directory

Machine-readable evaluation and acceptance evidence is written here. Generated reports are ignored by Git; this README is the tracked contract.

`make baseline` (U03) writes `reports/baseline/<run_id>/metrics.json`, containing test accuracy, macro-F1, weighted-F1, and per-class precision, recall, F1, and support for all 77 classes, alongside the provenance needed to reproduce them: `run_id`, dataset id and revision, the three split fingerprints, the label-map hash, the hash of the evaluated test example IDs, `metric_version`, `schema_version`, and dependency versions.

Test metrics are computed from the **reloaded** artifact, never from the in-memory model, and the test split is read exactly once per run. The selected hyperparameters are frozen in `configs/default.toml` and validated before any test read, so no metric here can have influenced model selection. Estimator options that were not selected keep their scikit-learn defaults, which is why each report records dependency versions.

`REQUIREMENTS.md` AC-002 requires `make baseline` to write test metrics, while `ARCHITECTURE.md` assigns test evaluation to `make evaluate`. `REQUIREMENTS.md` takes precedence, so the baseline report is written here.

U03 writes JSON only. Markdown rendering, calibration, coverage, selective risk, and latency reporting belong to later umbrellas, and none of those have been measured.
