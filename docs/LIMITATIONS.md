# Current limitations

The foundation, BANKING77 data contract, baseline, and transformer training path are implemented; strict MVP remains incomplete.

- BANKING77 is pinned to `1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`; data preparation validates its source split contract and records local provenance.
- The DistilBERT base model is pinned to `12040accade4e8a0f71eabdb258fecc2e7e948be` and one CPU fine-tune has been run. Its metrics are validation-only; the transformer has never been evaluated on the test split.
- Comparative evaluation, the FastAPI service, and the demo are not implemented.
- Measured metrics are limited to the baseline's test accuracy and macro-F1 and the transformer's validation accuracy, macro-F1, threshold, coverage, accepted accuracy, and selective risk. No calibration, test-split abstention, latency, or resource-efficiency metric has been measured, and no comparison between the two models exists.
- CUDA and GPU compatibility are unverified. CI is intentionally CPU-only.
- A synthetic dataset, frozen embeddings, deterministic API predictor, or one-epoch training path would be degraded evidence and cannot satisfy a violated MUST requirement.
- Docker and all deployment work are POST-WEEKEND.

See the authoritative [scope controls](specification/docs/SCOPE_CONTROL.md) and the local [parking lot](backlog/PARKING_LOT.md) for future boundaries.
