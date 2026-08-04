# Report directory

Machine-readable evaluation and acceptance evidence is written here. Generated reports are ignored by Git; this README is the tracked contract.

`make baseline` (U03) writes `reports/baseline/<run_id>/metrics.json`, containing test accuracy, macro-F1, weighted-F1, and per-class precision, recall, F1, and support for all 77 classes, alongside the provenance needed to reproduce them: `run_id`, dataset id and revision, the three split fingerprints, the label-map hash, the hash of the evaluated test example IDs, `metric_version`, `schema_version`, and dependency versions.

Test metrics are computed from the **reloaded** artifact, never from the in-memory model, and the test split is read exactly once per run. The selected hyperparameters are frozen in `configs/default.toml` and validated before any test read, so no metric here can have influenced model selection. Estimator options that were not selected keep their scikit-learn defaults, which is why each report records dependency versions.

`REQUIREMENTS.md` AC-002 requires `make baseline` to write test metrics, while `ARCHITECTURE.md` assigns test evaluation to `make evaluate`. `REQUIREMENTS.md` takes precedence, so the baseline report is written here.

`make train` (U04) writes `reports/train/<run_id>/training.json`, containing the per-epoch training loss and validation metrics, the selected threshold with its coverage, accepted accuracy and selective risk, the full risk/coverage curve, and the same provenance fields. It records no test-derived quantity: the threshold is selected from validation data only, and `make train` reads no test split. `provenance.json` inside the bundle is the authority for runtime facts.

`make evaluate` (U05) writes `reports/evaluate/<run_id>/comparison.json` and `reports/evaluate/<run_id>/comparison.md`. Both cover the same run: the JSON is the machine-readable evidence and the Markdown is a human-readable rendering of it, not an independent measurement.

`comparison.json` records the shared data identity both artifacts were checked against, the threshold with `reselected_during_evaluation: false`, full test metrics and selective-prediction figures for each model, the comparison verdict, the environment, and an explicit `limitations` array. Each model block records `evaluated_from: "reloaded_artifact"`, because a metric measured from an in-memory model would not evidence that the sealed bundle reproduces it.

The evaluation `run_id` is derived from everything that can change a reported number — both artifact run IDs, the split fingerprints, the label-map hash, the test example-ID hash, the threshold, and the metric and schema versions. Timings are deliberately excluded: wall-clock latency varies between two runs of the same configuration, so including it would give one evaluation two identities. This is why an evaluation report is rewritten in place on each run rather than sealed like an artifact bundle, and why rerunning `make evaluate` unchanged produces the same directory rather than a second one.

The baseline and transformer reports are JSON only; the evaluation report adds the Markdown rendering described above. Calibration error, risk/coverage over the test split, and latency reporting belong to S05.2, and the curated unsupported-request fixture to S05.3. None of those have been measured, which is why U05 is Partial rather than Implemented.

## The comparison outcome

The recorded verdict is `baseline_better`: test macro-F1 0.8654 for the baseline against 0.6620 for the transformer, a delta of -0.2034. `REQUIREMENTS.md` AC-004 requires the comparison to be written down whichever way it falls, so a report saying the transformer lost is a satisfied criterion. No configuration was altered after this was observed.

Test macro-F1 and weighted-F1 agree to reported precision here because the test split is exactly balanced at 40 examples per class, which makes the weights uniform. Do not read that agreement as evidence the two averaging modes are interchangeable, and do not use this report to check that they are wired correctly: it cannot tell them apart. `tests/fixtures/metric_regression.json` is deliberately imbalanced, so a macro/weighted swap fails a test there instead of passing silently here.
