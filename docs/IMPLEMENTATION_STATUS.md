# Implementation status

Status uses the repository vocabulary in `AGENTS.md`. `Measured` is an evidence qualifier and never substitutes for implementation.

| Umbrella | Capability | Status | Evidence |
|---|---|---|---|
| U01 | Project foundation and reproducibility | Implemented | Gate A local checks pass; CPU validation passed for `main` commit `1495776` ([run 30853223606](https://github.com/w7-mgfcode/intentguard/actions/runs/30853223606)) |
| U02 | BANKING77 data contract | Implemented | `make data` validated `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`: source 10,003/3,080, derived 8,502/1,501/3,080, 77 labels, deterministic fingerprints, and local provenance. |
| U03 | TF-IDF logistic-regression baseline | Implemented | `make baseline` produced run `intentguard-baseline-1fb62b1bb463-059ee4b12214` on `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`, measured from the reloaded artifact: test accuracy 0.8653, macro-F1 0.8654, 3,080 examples across 77 classes, seed 42. The test read here is documented divergence D1: `REQUIREMENTS.md` AC-002 requires `make baseline` to write test macro-F1 and outranks `ARCHITECTURE.md`. |
| U04 | DistilBERT training and immutable artifact | Implemented | `make train` sealed run `intentguard-distilbert-1fb62b1bb463-88e538757339` from `distilbert/distilbert-base-uncased@12040accade4e8a0f71eabdb258fecc2e7e948be`: measured validation accuracy 0.7162, macro-F1 0.6541, and threshold 0.1684 selected from validation confidences only at coverage 0.7015, accepted accuracy 0.8395, selective risk 0.1605. No test split was read, so this umbrella has no test metric. CPU-only by decision D10; `NFR-001`'s GPU clause stays unevidenced. |
| U05 | Comparative evaluation and selective prediction | Partial | `make evaluate` compares both sealed artifacts on the untouched test split as run `intentguard-evaluation-1fb62b1bb463-657900ed2e02`, applying the persisted validation threshold 0.16841767053420467 without reselecting it. Measured on 3,080 test examples: baseline accuracy 0.8653 / macro-F1 0.8654, transformer accuracy 0.6955 / macro-F1 0.6620, macro-F1 delta -0.2034, verdict `baseline_better`. Selective prediction at that threshold: baseline coverage 0.7500, accepted accuracy 0.9333, selective risk 0.0667; transformer coverage 0.6799, accepted accuracy 0.8161, selective risk 0.1839. Calibration Measured over 15 fixed equal-width bins: baseline ECE 0.4883 (mean confidence 0.3770 against accuracy 0.8653, 15/15 bins occupied), transformer ECE 0.4697 (mean confidence 0.2258 against accuracy 0.6955, 9/15 bins occupied); both are underconfident. Full risk/coverage curves are written for both models (3,074 and 3,081 points). Single-request latency Measured on the recorded CPU over 200 real test texts after 20 discarded warm-up requests: baseline p50 0.53 ms / p95 0.57 ms, transformer p50 10.68 ms / p95 13.06 ms — descriptive for that machine, not a service-level claim, and the only non-reproducing section of the report. The curated unsupported-request fixture is still absent, so this umbrella remains Partial and not Implemented; it is tracked by S05.3. |
| U06 | FastAPI inference and real-artifact demo | Planned | Backlog only |
| U07 | Full validation and acceptance gate | Planned | Backlog only |
| U08 | Documentation and recruiter-ready delivery | Planned | Foundation documents only; delivery work remains |

Strict MVP is not complete. The pinned dataset contract, both models' test metrics, the transformer's validation metrics and selected threshold, the test-split comparison and abstention behaviour, and both models' calibration and single-request CPU latency are Measured from executed local runs. No serving claim is Measured, and no GPU claim is evidenced.

U05 is Partial, so strict MVP is not satisfied by it. A MUST capability reported as Partial does not satisfy the strict-MVP gate regardless of how much of it is Measured.

## The transformer does not beat the baseline

The fine-tuned DistilBERT scored 0.2034 lower on test macro-F1 than the TF-IDF baseline. `REQUIREMENTS.md` AC-004 requires the comparison to be reported whichever way it falls, so this is a satisfied acceptance criterion and not a defect. At the frozen configuration — two CPU epochs, learning rate 2e-5, max sequence length 96 — the lexical baseline is the stronger model on this split.

No configuration, epoch count, seed, or threshold was changed in response to observing this result. Doing so would let a test label influence a modelling decision, which AC-005 forbids. The result stands as measured, and any future attempt to improve the transformer must be justified and validated without reading the test split.

## Neither model's confidence is a probability of correctness

Both models are substantially underconfident on the test split. The baseline reports a mean confidence of 0.3770 against an accuracy of 0.8653, and the transformer 0.2258 against 0.6955. Every occupied bin errs in the same direction for both models, which is why each ECE happens to equal its aggregate confidence-accuracy gap here; that is a property of this data, not of the metric, and the imbalanced fixture in `tests/fixtures/metric_regression.json` separates the two quantities (1/12 against 1/20).

The transformer's confidence never exceeded 0.6000 on any of the 3,080 test examples — six of the fifteen bins are empty. The persisted threshold of 0.1684 therefore has to be read relative to that range, not as a claimed probability of correctness. Reported because a reader who takes 0.1684 as a probability would conclude the system accepts almost anything, which is not what the coverage of 0.6799 shows.

No recalibration was applied. Temperature scaling or an equivalent fit would need its own validation-only evidence, and it is out of scope for the weekend MVP. Abstention here is a ranking decision over confidences, which underconfidence does not invalidate; the cost it imposes is coverage, since answers the model would have got right are discarded.
