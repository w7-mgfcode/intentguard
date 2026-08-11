# Evaluation

`make evaluate` loads both sealed bundles, proves they agree on their data provenance, applies the persisted threshold without reselecting it, and writes machine-readable evidence for every claim the README makes.

**Purpose:** what a valid comparison requires, what the run writes, and which part of the report legitimately differs between identical runs.
**Intended reader:** operators reproducing the measured results; anyone quoting a metric.

## What you'll accomplish

A `reports/` directory holding the evaluation run — `comparison.json`, risk/coverage curves, and the unsupported-fixture record — reproducing the numbers in [Interpreting results](interpreting-results.md). Prerequisites: both bundles from [Training](training.md); expect a roughly 30-second run, most of it latency measurement.

```bash
make evaluate
```

## Preconditions the run enforces

**Exactly one bundle per artifact directory.** `make evaluate` requires a single bundle under each of `artifacts/intentguard-baseline/` and `artifacts/intentguard-distilbert/`. A superseded sibling left beside a current bundle stops the run — it names both and refuses to guess, because attributing metrics to the wrong configuration is worse than failing. Remove the stale bundle and re-run ([Troubleshooting](../troubleshooting.md)).

**Provenance agreement.** Before predicting anything, the run proves the two bundles agree with each other and with the locally prepared splits on: dataset id, dataset revision, label-map hash, all three split fingerprints, and the hash of the evaluated test example IDs. Any disagreement is a hard failure — comparing two models trained on different data would produce a number that looks like a comparison but is not one.

**The threshold is applied, never derived.** The run reads the persisted value from the transformer bundle and applies it to test predictions. The evaluation script imports neither the selection function nor any fitting function, and a test inspects its syntax tree to keep it that way — re-deriving a threshold from test data is not something that code path can express.

## What the run measures

On the 3,080-example untouched test split, for both models, from their reloaded artifacts (U05):

- **Classification** — accuracy and macro-F1, and the comparison verdict (`baseline_better` in the recorded run, delta −0.2034 macro-F1).
- **Selective prediction** — coverage, accepted accuracy, and selective risk at the persisted threshold, plus full risk/coverage curves (3,074 and 3,081 points).
- **Calibration** — expected calibration error over 15 fixed equal-width bins, with per-bin occupancy.
- **The curated unsupported-request check** — all 12 hand-written rows decided once each at the same persisted threshold, written separately to `unsupported_fixture.json` and `unsupported_fixture.md`. The run fails loudly if the fixture is missing, malformed, or collides with any BANKING77 split: a fixture row that exists in training data would make its abstention a measure of memorisation, so that is an authoring error to fix, not something the run works around.
- **Single-request latency** — batch size 1 over 200 real test texts after 20 discarded warm-up requests, measured last, from the same reloaded artifacts.

## Reading the output

Reports land under `reports/` (Git-ignored; [reports/README.md](../../../reports/README.md) is the tracked contract describing every file). The run directory is named by a content-derived run ID — `intentguard-evaluation-1fb62b1bb463-55796a53ca3e` in the recorded run.

**One section legitimately does not reproduce: latency.** Two consecutive runs of the same configuration produce the same run ID, the same directory, and byte-identical metrics — but different p50/p95 latency values. That is intended, not a defect: the run ID covers the sampling *protocol* (sample count, warm-up count, seed), never the measured durations, which is also why re-running rewrites the directory in place. Quote latency only from a report you have in hand, as a range, tied to its machine ([Interpreting results](interpreting-results.md)).

Everything else in `comparison.json` is deterministic. The recorded headline numbers, at the persisted threshold `0.16841767053420467`:

| Metric | TF-IDF baseline | DistilBERT |
|---|---|---|
| Accuracy | 0.8653 | 0.6955 |
| Macro-F1 | 0.8654 | 0.6620 |
| Coverage | 0.7500 | 0.6799 |
| Accepted accuracy | 0.9333 | 0.8161 |
| Selective risk | 0.0667 | 0.1839 |
| ECE (15 bins) | 0.4883 | 0.4697 |

Nothing was retuned after these numbers were seen — that discipline is the point of the pipeline ([LIMITATIONS.md](../../LIMITATIONS.md)).

## Next

[Serving](serving.md) — put the sealed transformer bundle behind HTTP. Or jump to [Interpreting results](interpreting-results.md) for what these numbers mean.
