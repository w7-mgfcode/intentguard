# Implementation status

Status uses the repository vocabulary in `AGENTS.md`. `Measured` is an evidence qualifier and never substitutes for implementation.

| Umbrella | Capability | Status | Evidence |
|---|---|---|---|
| U01 | Project foundation and reproducibility | Implemented | Gate A local checks pass; CPU validation passed for `main` commit `1495776` ([run 30853223606](https://github.com/w7-mgfcode/intentguard/actions/runs/30853223606)) |
| U02 | BANKING77 data contract | Implemented | `make data` validated `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`: source 10,003/3,080, derived 8,502/1,501/3,080, 77 labels, deterministic fingerprints, and local provenance. |
| U03 | TF-IDF logistic-regression baseline | Implemented | `make baseline` produced run `intentguard-baseline-1fb62b1bb463-059ee4b12214` on `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`, measured from the reloaded artifact: test accuracy 0.8653, macro-F1 0.8654, 3,080 examples across 77 classes, seed 42. The test read here is documented divergence D1: `REQUIREMENTS.md` AC-002 requires `make baseline` to write test macro-F1 and outranks `ARCHITECTURE.md`. |
| U04 | DistilBERT training and immutable artifact | Implemented | `make train` sealed run `intentguard-distilbert-1fb62b1bb463-88e538757339` from `distilbert/distilbert-base-uncased@12040accade4e8a0f71eabdb258fecc2e7e948be`: measured validation accuracy 0.7162, macro-F1 0.6541, and threshold 0.1684 selected from validation confidences only at coverage 0.7015, accepted accuracy 0.8395, selective risk 0.1605. No test split was read, so this umbrella has no test metric. CPU-only by decision D10; `NFR-001`'s GPU clause stays unevidenced. |
| U05 | Comparative evaluation and selective prediction | Planned | Backlog only |
| U06 | FastAPI inference and real-artifact demo | Planned | Backlog only |
| U07 | Full validation and acceptance gate | Planned | Backlog only |
| U08 | Documentation and recruiter-ready delivery | Planned | Foundation documents only; delivery work remains |

Strict MVP is not complete. The pinned dataset contract, the baseline's test metrics, and the transformer's validation metrics and selected threshold are Measured from executed local runs. No comparative test evaluation, calibration, test-split abstention, latency, or serving claim is Measured, and no GPU claim is evidenced.
