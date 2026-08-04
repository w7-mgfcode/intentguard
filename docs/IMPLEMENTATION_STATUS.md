# Implementation status

Status uses the repository vocabulary in `AGENTS.md`. `Measured` is an evidence qualifier and never substitutes for implementation.

| Umbrella | Capability | Status | Evidence |
|---|---|---|---|
| U01 | Project foundation and reproducibility | Implemented | Gate A local checks pass; CPU validation passed for `main` commit `1495776` ([run 30853223606](https://github.com/w7-mgfcode/intentguard/actions/runs/30853223606)) |
| U02 | BANKING77 data contract | Implemented | `make data` validated `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`: source 10,003/3,080, derived 8,502/1,501/3,080, 77 labels, deterministic fingerprints, and local provenance. |
| U03 | TF-IDF logistic-regression baseline | Implemented | `make baseline` produced run `intentguard-baseline-1fb62b1bb463-059ee4b12214` on `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`, measured from the reloaded artifact: test accuracy 0.8653, macro-F1 0.8654, 3,080 examples across 77 classes, seed 42. The test read here is documented divergence D1: `REQUIREMENTS.md` AC-002 requires `make baseline` to write test macro-F1 and outranks `ARCHITECTURE.md`. |
| U04 | DistilBERT training and immutable artifact | Implemented | `make train` sealed run `intentguard-distilbert-1fb62b1bb463-88e538757339` from `distilbert/distilbert-base-uncased@12040accade4e8a0f71eabdb258fecc2e7e948be`: measured validation accuracy 0.7162, macro-F1 0.6541, and threshold 0.1684 selected from validation confidences only at coverage 0.7015, accepted accuracy 0.8395, selective risk 0.1605. No test split was read, so this umbrella has no test metric. CPU-only by decision D10; `NFR-001`'s GPU clause stays unevidenced. |
| U05 | Comparative evaluation and selective prediction | Partial | `make evaluate` compares both sealed artifacts on the untouched test split as run `intentguard-evaluation-1fb62b1bb463-e136e274da44`, applying the persisted validation threshold 0.16841767053420467 without reselecting it. Measured on 3,080 test examples: baseline accuracy 0.8653 / macro-F1 0.8654, transformer accuracy 0.6955 / macro-F1 0.6620, macro-F1 delta -0.2034, verdict `baseline_better`. Selective prediction at that threshold: baseline coverage 0.7500, accepted accuracy 0.9333, selective risk 0.0667; transformer coverage 0.6799, accepted accuracy 0.8161, selective risk 0.1839. Calibration error, risk/coverage curves, latency, and the curated unsupported-request fixture are absent, so this umbrella is Partial and not Implemented; they are tracked by S05.2 and S05.3. |
| U06 | FastAPI inference and real-artifact demo | Planned | Backlog only |
| U07 | Full validation and acceptance gate | Planned | Backlog only |
| U08 | Documentation and recruiter-ready delivery | Planned | Foundation documents only; delivery work remains |

Strict MVP is not complete. The pinned dataset contract, both models' test metrics, the transformer's validation metrics and selected threshold, and the test-split comparison and abstention behaviour are Measured from executed local runs. No calibration, latency, or serving claim is Measured, and no GPU claim is evidenced.

U05 is Partial, so strict MVP is not satisfied by it. A MUST capability reported as Partial does not satisfy the strict-MVP gate regardless of how much of it is Measured.

## The transformer does not beat the baseline

The fine-tuned DistilBERT scored 0.2034 lower on test macro-F1 than the TF-IDF baseline. `REQUIREMENTS.md` AC-004 requires the comparison to be reported whichever way it falls, so this is a satisfied acceptance criterion and not a defect. At the frozen configuration — two CPU epochs, learning rate 2e-5, max sequence length 96 — the lexical baseline is the stronger model on this split.

No configuration, epoch count, seed, or threshold was changed in response to observing this result. Doing so would let a test label influence a modelling decision, which AC-005 forbids. The result stands as measured, and any future attempt to improve the transformer must be justified and validated without reading the test split.
