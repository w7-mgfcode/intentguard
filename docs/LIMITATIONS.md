# Current limitations

Gate A establishes repository structure and planning evidence only.

- BANKING77 has not been downloaded or validated; its immutable revision is unresolved.
- The DistilBERT base-model revision is unresolved and no weights have been loaded.
- The baseline, fine-tuning, threshold selection, evaluation, FastAPI service, and demo are not implemented.
- No accuracy, macro-F1, calibration, coverage, selective-risk, abstention, latency, or resource metric has been measured.
- CUDA and GPU compatibility are unverified. CI is intentionally CPU-only.
- A synthetic dataset, frozen embeddings, deterministic API predictor, or one-epoch training path would be degraded evidence and cannot satisfy a violated MUST requirement.
- Docker and all deployment work are POST-WEEKEND.

See the authoritative [scope controls](specification/docs/SCOPE_CONTROL.md) and the local [parking lot](backlog/PARKING_LOT.md) for future boundaries.
