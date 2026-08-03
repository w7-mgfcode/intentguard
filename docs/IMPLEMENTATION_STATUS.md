# Implementation status

Status uses the repository vocabulary in `AGENTS.md`. `Measured` is an evidence qualifier and never substitutes for implementation.

| Umbrella | Capability | Status | Evidence |
|---|---|---|---|
| U01 | Project foundation and reproducibility | Implemented | Gate A local checks pass; remote CPU CI remains unexecuted until later approval |
| U02 | BANKING77 data contract | Implemented | `make data` validated `PolyAI/banking77@1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8`: source 10,003/3,080, derived 8,502/1,501/3,080, 77 labels, deterministic fingerprints, and local provenance. |
| U03 | TF-IDF logistic-regression baseline | Planned | Backlog only |
| U04 | DistilBERT training and immutable artifact | Planned | Backlog only |
| U05 | Comparative evaluation and selective prediction | Planned | Backlog only |
| U06 | FastAPI inference and real-artifact demo | Planned | Backlog only |
| U07 | Full validation and acceptance gate | Planned | Backlog only |
| U08 | Documentation and recruiter-ready delivery | Planned | Foundation documents only; delivery work remains |

Strict MVP is not complete. The pinned dataset contract is measured from executed local provenance; no model, evaluation, latency, calibration, or serving claim is Measured.
