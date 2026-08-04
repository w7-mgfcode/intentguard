# Scripts

This directory owns local developer entry points. `prepare_data.py` implements
U02 by loading the pinned BANKING77 revision, validating its data contract, and
writing ignored local provenance. `train_baseline.py` implements U03 and
`train_transformer.py` implements U04. `evaluate.py` implements U05: it loads both
sealed bundles, proves they describe the same data as each
other and as the locally prepared splits, applies the persisted validation
threshold verbatim, and writes the test-split comparison together with per-model
calibration, risk/coverage curves, single-request latency, and the curated
unsupported-request check. Service and demo scripts remain planned under U06.

The curated fixture is decided through the transformer, because that is the model
serving will load, and its texts are asserted disjoint from all three BANKING77
splits **before** any prediction is made — checking afterwards would mean a colliding
row had already contributed a number to the report.

`evaluate.py` deliberately imports no threshold-selection or model-fitting
function, so no test label can reach a modelling decision through it. A test
enforces that by parsing the script's syntax tree, because a text search would be
satisfied by the words appearing in these comments.

The test split is read exactly once per run. Calibration and the risk/coverage
curve reuse the confidences already derived for the selective-prediction figures,
and every probability matrix is checked to sum to one per row before any of them is
consumed — the maximum of a row is only a confidence if the row is a distribution,
and a softmax-axis mistake would otherwise surface as a believable abstention rate
rather than as a failure. A test asserts that ordering against the syntax tree.

Latency measurement loads each model outside the timed region, because a request in
service does not pay artifact loading and re-hashing, and keeps tokenisation inside
it, because a request does pay that.
