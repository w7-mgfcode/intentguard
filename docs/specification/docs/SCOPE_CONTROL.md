# Scope-Control System

## Frozen MVP checklist

Before starting implementation, confirm:

- [ ] One primary dataset: BANKING77.
- [ ] One baseline: TF-IDF plus logistic regression.
- [ ] One improved model: fine-tuned DistilBERT.
- [ ] One inference interface: FastAPI.
- [ ] One artifact location: local filesystem.
- [ ] One evaluation pipeline.
- [ ] One documented local environment path.
- [ ] No generated metric or business claim.
- [ ] No additional service, database, model, dataset, or frontend.

Any change to these statements is a scope change, not an implementation detail.

## Working-baseline-first checkpoint

By Hour 6:

- validated data exists;
- the baseline trains;
- the artifact reloads;
- test metrics are generated;
- metric unit tests pass.

Transformer work cannot begin before this checkpoint.

## Time-boxing rules

1. Every blocker receives at most 30 focused minutes before using its documented
   fallback or reporting the block.
2. Data download/debugging receives at most 45 minutes.
3. GPU environment troubleshooting receives at most 45 minutes before CPU
   baseline work continues.
4. Fine-tuning receives one normal run and one memory-adjusted retry.
5. Hyperparameter exploration is prohibited.
6. Documentation is updated as tasks close, not postponed entirely to the end.
7. At each hour boundary, compare remaining MUST work with remaining time.
8. SHOULD and STRETCH tasks may start only when every MUST task has a passing
   validation path.

## Fallbacks

| Problem | Fallback | Consequence |
|---|---|---|
| Dataset unavailable | Verified cache, else synthetic fallback | No BANKING77 benchmark claims |
| CUDA unavailable | Continue data/baseline/API tests on CPU | Transformer training may be blocked/partial |
| CUDA OOM | Batch 8, eval batch 16 | Slower training; same architecture |
| Training too slow | One epoch | Report reduced training budget |
| Fine-tuning integration fails | Frozen DistilBERT embeddings plus logistic regression | Mark FR-003 partial; rename claims accurately |
| Calibration code delayed | Keep risk/coverage and global threshold; cut temperature scaling | No calibrated-model claim |
| API delayed | Keep only two endpoints and deterministic test predictor | Do not add CLI inference |
| Latency unstable | Increase repetitions and report environment/noise | No latency target claim |
| README delayed | Use generated evaluation table and concise limitation list | Cut visual polish, not truthfulness |

## Criteria for removing a feature

Remove or defer a feature when:

- it is not required by an FR/AC;
- it introduces a new persistent component or runtime process;
- it cannot be tested within its time box;
- it lacks a meaningful metric;
- it duplicates another interface;
- it weakens completion of the vertical slice;
- its claim would exceed available evidence.

## Cut order if behind

1. Temperature scaling.
2. Additional plots or rich report styling.
3. Per-class narrative beyond the top confusion pairs.
4. Docker.
5. Expanded unsupported-query fixture.
6. CI tiny-training smoke if runtime is excessive; retain unit/API CI.
7. Any second model, endpoint, interface, or dataset—which should never have
   entered MUST scope.

Do not cut:

- baseline comparison;
- saved-artifact reload;
- validation-only threshold selection;
- critical API validation;
- evaluation regression test;
- honest limitations;
- requirement-to-test traceability.

## Sunday completion gate

At Hour 13, all of these must be true:

- [ ] baseline artifact reloads;
- [ ] transformer or explicitly documented fallback artifact reloads;
- [ ] comparison report exists;
- [ ] threshold was selected without test-label access;
- [ ] API loads the artifact;
- [ ] health check passes;
- [ ] one valid request completes;
- [ ] critical unit and API tests have a passing path.

If the gate fails, freeze documentation polish and fix only these items.

## Feature parking lot

### SHOULD

- temperature scaling;
- short top-confusion-pair commentary.

### STRETCH

- CPU-only Docker inference image;
- one compact evaluation chart generated from real metrics.

### POST-WEEKEND

- multilingual evaluation;
- per-class thresholds;
- stronger OOD dataset;
- quantization or ONNX export;
- batch endpoint;
- ticket-system adapter;
- drift analysis;
- human-review workflow;
- cloud deployment;
- load testing.

Parking-lot items are not promises or automatic roadmap commitments.

## Change request template

```text
Requested feature:
Requirement served:
Why current design is insufficient:
Added dependency/component:
Estimated hours:
Test and metric:
MUST task displaced:
Decision: reject / park / approve with ADR
```

