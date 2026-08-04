# Current limitations

The foundation, BANKING77 data contract, baseline, and transformer training path are implemented; comparative evaluation is partial; strict MVP remains incomplete.

- BANKING77 is pinned to `1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`; data preparation validates its source split contract and records local provenance.
- The DistilBERT base model is pinned to `12040accade4e8a0f71eabdb258fecc2e7e948be` and one CPU fine-tune has been run.
- **The fine-tuned transformer loses to the lexical baseline.** On the test split its macro-F1 is 0.6620 against the baseline's 0.8654, a shortfall of 0.2034. This is a measured outcome reported as AC-004 requires, not a defect and not a pending fix. It reflects the frozen configuration in `configs/default.toml` — two CPU epochs at learning rate 2e-5 — and should not be read as a statement about DistilBERT's ceiling on BANKING77.
- Nothing was tuned in response to that result. Changing a configuration, seed, epoch count, or threshold after observing test metrics would breach the AC-005 leakage controls, so the number stands as measured.
- `make evaluate` is implemented but U05 is **Partial**: expected calibration error, the risk/coverage curve over the test split, latency measurement, and the curated unsupported-request fixture are absent. They are tracked by S05.2 and S05.3, and U05 becomes Implemented only when they exist.
- The FastAPI service and the demo are not implemented.
- Measured metrics are the baseline's and transformer's test accuracy, macro-F1, weighted-F1, and per-class figures; the transformer's validation metrics and selected threshold; and both models' test coverage, accepted accuracy, and selective risk at that threshold. No calibration, latency, or resource-efficiency metric has been measured.
- Test macro-F1 and weighted-F1 agree to reported precision for both models because the test split is exactly balanced at 40 examples per class, so the weights are uniform. They are not bit-identical — the transformer's differ in the final floating-point digit because the two averages sum in different orders — but no meaningful comparison distinguishes them on this split. That agreement is a property of the split, not evidence that the two averaging modes are interchangeable; the deliberately imbalanced fixture in `tests/fixtures/metric_regression.json` is what distinguishes them, and a swap between them fails there.
- Both models were evaluated at the same threshold, which was selected from the transformer's validation confidences. It is not a baseline-optimal operating point, so the baseline's selective figures describe its behaviour at a borrowed threshold rather than its best achievable trade-off.
- CUDA and GPU compatibility are unverified. CI is intentionally CPU-only.
- A synthetic dataset, frozen embeddings, deterministic API predictor, or one-epoch training path would be degraded evidence and cannot satisfy a violated MUST requirement.
- Docker and all deployment work are POST-WEEKEND.

See the authoritative [scope controls](specification/docs/SCOPE_CONTROL.md) and the local [parking lot](backlog/PARKING_LOT.md) for future boundaries.
