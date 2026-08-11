# Interpreting results

Every metric IntentGuard reports, what it commits to, and — just as important here — what it does not.

**Purpose:** make the numbers in the README, the reports, and the API responses readable without over-reading them.
**Intended reader:** operators and reviewers quoting results; complements [LIMITATIONS.md](../../LIMITATIONS.md), which is authoritative on what the numbers do not support.

## What you'll accomplish

After this chapter, given any row of `comparison.json` or any API response, you can say precisely what was measured, over which examples, and which caveats travel with it.

## The classification metrics

**Accuracy** — the fraction of the 3,080 test examples whose predicted intent matches the label. Baseline 0.8653, transformer 0.6955 in the recorded run.

**Macro-F1** — the F1 score computed per intent and averaged over all 77 intents with equal weight, so rare intents count as much as common ones. This is the comparison's headline metric: baseline 0.8654, transformer 0.6620, delta −0.2034, verdict `baseline_better`. The verdict is a recorded field in the report, not a narrative judgement. It reflects the frozen two-CPU-epoch configuration and is not a statement about DistilBERT's ceiling on BANKING77.

## The selective-prediction metrics

These describe behavior *at the persisted threshold* (`0.16841767053420467` in the recorded artifacts):

**Coverage** — the fraction of examples the model accepts (does not abstain on). Baseline 0.7500, transformer 0.6799 on test. Equivalently: the transformer abstained on 0.3201 of the test split.

**Accepted accuracy** — accuracy among accepted examples only. Baseline 0.9333, transformer 0.8161. This is the number abstention buys: by declining its least-confident predictions, the baseline converts 0.8653 overall accuracy into 0.9333 accuracy on what it does answer.

**Selective risk** — the error rate among accepted examples: `1 − accepted accuracy`. Baseline 0.0667, transformer 0.1839. The threshold was selected to minimise exactly this quantity on validation data, subject to a coverage floor of 0.70 ([Training](training.md)).

**The risk/coverage curve** — the full trade-off: every candidate threshold, with its coverage and selective risk. The persisted threshold is one point on this curve, chosen by the frozen rule; the curve shows what other operating points would have cost.

## What a confidence is — and is not

**A confidence here is a ranking signal for abstention, not a probability of correctness.** Both models are substantially underconfident: the baseline's mean confidence is 0.3770 against 0.8653 accuracy; the transformer's is 0.2258 against 0.6955. No recalibration was applied — it would require its own validation-only evidence and is out of scope.

Underconfidence does not break abstention, because abstention only needs confidences to *rank* examples. The cost it imposes is coverage: answers the model would have got right are discarded.

Read the threshold in that light. `0.1684` looks low against an imagined 0-to-1 probability scale, but the transformer's confidence never exceeded 0.6000 on any test example — the threshold is meaningful relative to that observed range, not as an absolute probability.

**ECE (expected calibration error)** — measured over 15 fixed equal-width bins: baseline 0.4883 (all 15 bins occupied), transformer 0.4697 (9 of 15 occupied). These large values are the quantified form of "confidence is not a probability of correctness". Note the trap: the transformer's *lower* ECE does not mean it is the better model — it is less accurate and covers less; it is merely differently miscalibrated.

## The unsupported-request check

Twelve hand-written requests across six declared categories (other-domain, prompt injection, nonsense, empty, non-English, adjacent-banking), all of which abstained at the persisted threshold. Read this as **a passed behavioral check, not an out-of-distribution benchmark**: an abstention rate over a fixture its author chose is partly a statement about that author's imagination.

The number is only meaningful beside its in-distribution contrast: mean confidence 0.0503 on the fixture against 0.2258 on the test split, where 0.3201 of examples also abstain. A total abstention rate alone would be indistinguishable from a model that abstains on everything. No accuracy is reported for the fixture — no BANKING77 intent is correct for any of its rows, so accuracy is undefined there, not merely unmeasured.

## Latency

Single-request latency, batch size 1, one CPU machine, 200 real test texts after 20 discarded warm-ups: baseline p50 near 0.55 ms; transformer p50 between roughly 8.6 and 10.7 ms across runs, p95 near 11 ms. Three caveats, all deliberate:

- **Descriptive for that machine, not a service level.** It does not generalise to other hardware.
- **It is the one section of the report that does not reproduce** between runs of the same configuration — the run ID covers the sampling protocol, never the durations ([Evaluation](evaluation.md)).
- **Quote from a report you have in hand**, as a range, never from memory or from this page.

The `latency_ms` field in an API response is a different quantity again: the inference window of one request inside the server process — a lower bound on the contract's definition, excluding network time ([API reference](../integrator/api-reference.md)).

## Where the authoritative numbers live

Per-capability evidence, run IDs, and the strict-MVP verdict: [IMPLEMENTATION_STATUS.md](../../IMPLEMENTATION_STATUS.md). What the numbers cannot support: [LIMITATIONS.md](../../LIMITATIONS.md). The reports your own machine writes: `make evaluate`, described in [reports/README.md](../../../reports/README.md).

## Next

Operator track complete. For the API and artifact internals, continue to the [Integrator track](../README.md#two-tracks); for term lookups, the [Glossary](../glossary.md).
