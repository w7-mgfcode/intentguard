# Report directory

Machine-readable evaluation and acceptance evidence is written here. Generated reports are ignored by Git; this README is the tracked contract.

`make baseline` (U03) writes `reports/baseline/<run_id>/metrics.json`, containing test accuracy, macro-F1, weighted-F1, and per-class precision, recall, F1, and support for all 77 classes, alongside the provenance needed to reproduce them: `run_id`, dataset id and revision, the three split fingerprints, the label-map hash, the hash of the evaluated test example IDs, `metric_version`, `schema_version`, and dependency versions.

Test metrics are computed from the **reloaded** artifact, never from the in-memory model, and the test split is read exactly once per run. The selected hyperparameters are frozen in `configs/default.toml` and validated before any test read, so no metric here can have influenced model selection. Estimator options that were not selected keep their scikit-learn defaults, which is why each report records dependency versions.

`REQUIREMENTS.md` AC-002 requires `make baseline` to write test metrics, while `ARCHITECTURE.md` assigns test evaluation to `make evaluate`. `REQUIREMENTS.md` takes precedence, so the baseline report is written here.

`make train` (U04) writes `reports/train/<run_id>/training.json`, containing the per-epoch training loss and validation metrics, the selected threshold with its coverage, accepted accuracy and selective risk, the full risk/coverage curve, and the same provenance fields. It records no test-derived quantity: the threshold is selected from validation data only, and `make train` reads no test split. `provenance.json` inside the bundle is the authority for runtime facts.

`make evaluate` (U05) writes `reports/evaluate/<run_id>/comparison.json` and `reports/evaluate/<run_id>/comparison.md`. Both cover the same run: the JSON is the machine-readable evidence and the Markdown is a human-readable rendering of it, not an independent measurement.

`comparison.json` records the shared data identity both artifacts were checked against, the threshold with `reselected_during_evaluation: false`, full test metrics and selective-prediction figures for each model, per-model calibration and the full risk/coverage curve, per-model single-request latency, the comparison verdict, the latency protocol and its environment, and an explicit `limitations` array. Each model block records `evaluated_from: "reloaded_artifact"`, because a metric measured from an in-memory model would not evidence that the sealed bundle reproduces it.

The evaluation `run_id` is derived from everything that can change a reported number — both artifact run IDs, the split fingerprints, the label-map hash, the test example-ID hash, the threshold, the metric and schema versions, the calibration bin count and binning, and the latency sampling protocol. Timings are deliberately excluded: wall-clock latency varies between two runs of the same configuration, so including it would give one evaluation two identities. This is why an evaluation report is rewritten in place on each run rather than sealed like an artifact bundle, and why rerunning `make evaluate` unchanged produces the same directory rather than a second one.

The baseline and transformer reports are JSON only; the evaluation report adds the Markdown rendering described above.

`make evaluate` also writes `reports/evaluate/<run_id>/unsupported_fixture.json` and `unsupported_fixture.md` for the curated unsupported-request check (FR-009, AC-012). It is kept in its own pair of files, and mirrored as one block inside `comparison.json`, because it is a different kind of evidence from the test-split metrics beside it: a hand-written fixture cannot be pooled with a measured split without implying it was sampled the same way.

Editing that fixture changes the evaluation `run_id`. Its bytes are hashed into the run identity alongside its schema version, so a reworded request yields a new identity rather than silently reusing one — but the hash is identity input only and is not itself a report field.

Both files carry the mandated caveat verbatim and state that no accuracy is reported, because no BANKING77 intent is correct for any curated row. The Markdown renderer refuses outright to print a total abstention rate without the in-distribution rate beside it: "abstained on all 12" without "and accepted most of the test split" is the sentence a reader would mistake for detection evidence, so the failure is loud instead of flattering.

## Calibration and latency

Expected calibration error uses 15 fixed equal-width bins, left-closed and right-open, with the final bin closed at 1.0 so a confidence of exactly 1.0 is binned rather than dropped. Equal width rather than equal mass: equal-mass edges are derived from the data, so two models would be scored against two different binnings and their ECEs would not be comparable, which is the only thing the metric is here to do.

Empty bins are recorded for transparency but excluded from the average. Counting an empty bin's gap as a real zero and dividing by the bin count would scale ECE by `non_empty / bin_count` and flatter a badly calibrated model; on the measured run that would understate the baseline by 18.7% and the transformer by 39.4%. Two ECEs are comparable only when computed under the same binning.

Both models are underconfident on this split — baseline ECE 0.4883 at mean confidence 0.3770 against accuracy 0.8653, transformer ECE 0.4697 at 0.2258 against 0.6955 — and the transformer's confidence never exceeded 0.6000, leaving six bins empty. A confidence from either model is a ranking signal for abstention, not a probability of correctness. Each ECE happens to equal its aggregate confidence-accuracy gap here because every occupied bin errs in the same direction; that is a property of this data, and the imbalanced fixture separates the two quantities as 1/12 against 1/20.

Latency is the one section that does not reproduce. It is measured at batch size 1 over 200 real test texts drawn by a seeded permutation — not the first 200 rows, which arrive grouped by label and would over-represent a few phrasing lengths — after 20 discarded warm-up requests, with tokenisation inside the timed region and artifact loading outside it. Percentiles are nearest-rank, so every reported value is a duration that was actually observed rather than an interpolation. The measurement is descriptive for the machine recorded in the report and is not a service-level claim; both files carry that caveat verbatim, and the renderer refuses to print a percentile without it.

## The comparison outcome

The recorded verdict is `baseline_better`: test macro-F1 0.8654 for the baseline against 0.6620 for the transformer, a delta of -0.2034. `REQUIREMENTS.md` AC-004 requires the comparison to be written down whichever way it falls, so a report saying the transformer lost is a satisfied criterion. No configuration was altered after this was observed.

Test macro-F1 and weighted-F1 agree to reported precision here because the test split is exactly balanced at 40 examples per class, which makes the weights uniform. Do not read that agreement as evidence the two averaging modes are interchangeable, and do not use this report to check that they are wired correctly: it cannot tell them apart. `tests/fixtures/metric_regression.json` is deliberately imbalanced, so a macro/weighted swap fails a test there instead of passing silently here.
