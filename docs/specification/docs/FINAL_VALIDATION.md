# Final Validation

## Validation verdict

The frozen design is realistic for one focused weekend, provided the developer
reaches the working-baseline checkpoint by Hour 6 and does not expand the
architecture.

## Critical verification

### Can it be completed in 12–16 hours?

**Yes, with moderate risk.**

The baseline, dataset and evaluation components are small. Fine-tuning and
environment setup are the primary risks. The plan limits these through one
checkpoint, one OOM retry, one epoch fallback, and a documented degraded model
fallback.

### Does it run on the specified laptop?

**Expected yes, subject to environment validation.**

DistilBERT, BANKING77 and the baseline fit well within 24 GB RAM. Conservative
sequence length and batch size target the mobile GPU. CPU inference is required;
CPU full training is not a weekend guarantee.

### Is there a meaningful baseline?

**Yes.**

Word TF-IDF plus logistic regression is a strong, interpretable short-text
baseline and can reveal whether the transformer provides actual value.

### Are results measurable and reproducible?

**Yes, within documented limits.**

The design fixes split behavior, revisions, seeds, metrics, threshold policy,
artifact provenance and lockfile. It explicitly avoids promising bitwise
identity across hardware/software releases.

### Does it demonstrate real ML engineering?

**Yes.**

Evidence includes data contracts, baseline comparison, transformer fine-tuning,
artifact reload, calibration diagnostics, selective prediction, latency,
interface validation and evaluation regression tests.

### Is every infrastructure component justified?

**Yes.**

- FastAPI creates the only public boundary.
- Local filesystem is enough for one artifact.
- Lockfile and CI provide proportional reproducibility.
- No database, queue, registry, vector store, cloud or monitoring platform is
  present.

### Can coding agents implement without redesigning?

**Yes.**

Requirements, boundaries, commands, file targets, acceptance criteria,
traceability, stop rules and ADRs are explicit. `AGENTS.md` forbids
architectural expansion.

### Are claims and limitations honest?

**Yes, if implementation follows the reporting rules.**

Model improvement is a hypothesis, not an assumption. Unsupported-query
behavior is separated from benchmark results. Example response numbers are
marked illustrative.

### Is it easy to demonstrate?

**Yes.**

The five-minute path shows a result table, architecture, health check, accepted
prediction, abstention, tests and one limitation.

## Components removed during validation

- Temperature scaling removed from MUST scope.
- Docker moved after the weekend.
- CLI inference removed to keep one interface.
- General OOD claims rejected.
- Multi-model comparison rejected.
- Frontend rejected.
- Database, registry and monitoring stack rejected.
- LLM explanations and agent workflows rejected as unrelated to the selected
  problem.
- Per-class thresholds moved after the weekend.

## Remaining assumptions to validate early

1. Compatible PyTorch/CUDA installation.
2. Pinned Hugging Face dataset and model revisions.
3. Full label mapping returned by the loader.
4. Fine-tuning memory at batch size 16.
5. Training duration under the allocated time.

## Final scope statement

> One validated banking-intent dataset, one lexical baseline, one DistilBERT
> classifier, one validation-derived abstention policy, one evaluation pipeline,
> one local artifact bundle, one FastAPI interface, focused tests, and honest
> documentation.

Any requested addition must displace an existing component or wait until after
the Sunday completion gate.

