# Scripts

This directory owns local developer entry points. `prepare_data.py` implements
U02 by loading the pinned BANKING77 revision, validating its data contract, and
writing ignored local provenance. `train_baseline.py` implements U03 and
`train_transformer.py` implements U04. `evaluate.py` implements the measured part
of U05: it loads both sealed bundles, proves they describe the same data as each
other and as the locally prepared splits, applies the persisted validation
threshold verbatim, and writes the test-split comparison. U05 is Partial —
calibration, latency, and the unsupported-request fixture are outstanding. Service
and demo scripts remain planned under U06.

`evaluate.py` deliberately imports no threshold-selection or model-fitting
function, so no test label can reach a modelling decision through it. A test
enforces that by parsing the script's syntax tree, because a text search would be
satisfied by the words appearing in these comments.
