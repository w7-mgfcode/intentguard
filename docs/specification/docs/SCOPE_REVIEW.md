# Pre-Documentation Scope Review

## Architecture challenge

Every Phase 1 component was challenged against one question:

> Is this required to demonstrate the complete train-evaluate-serve-abstain
> vertical slice within 12–16 hours?

| Proposed component | Decision | Reason |
|---|---|---|
| BANKING77 | Keep | One public, fine-grained, laptop-sized primary dataset |
| Stratified validation split | Keep | Required for epoch and threshold selection without test leakage |
| TF-IDF logistic baseline | Keep | Meaningful reference with low implementation cost |
| Fine-tuned DistilBERT | Keep | Core PyTorch/Hugging Face evidence |
| Global abstention threshold | Keep | Changes a forced classifier into a safer decision boundary |
| Risk/coverage evaluation | Keep | Necessary to evaluate abstention honestly |
| Small unsupported fixture | Keep, narrow | Behavioral demonstration only; not a general OOD benchmark |
| Temperature scaling | Move to SHOULD | Useful but not required for the vertical slice |
| Per-class thresholds | Post-weekend | Adds policy and data-sufficiency complexity |
| FastAPI | Keep | Provides one typed production boundary |
| CLI inference | Remove | Duplicates the public interface |
| Health check | Keep | Small and directly validates artifact readiness |
| Local artifact metadata | Keep | Required to reload and reproduce the evaluated model |
| Docker | Post-weekend | GPU/WSL packaging risk displaces ML validation |
| Structured logs | Keep, minimal | One privacy-conscious event per request is proportional |
| Dashboard/monitoring | Remove | No continuous deployment or traffic exists |
| Database/model registry | Remove | One immutable local artifact does not justify them |
| Frontend | Remove | Curl/OpenAPI is sufficient for a five-minute demo |
| Cloud deployment | Post-weekend | Not required and no target platform is known |
| Hyperparameter search | Remove | One model configuration answers the portfolio question |
| LLM explanations | Remove | Creates an unevaluated second model problem |

## Smallest meaningful vertical slice

```text
BANKING77
  -> validated train/validation/test data
  -> TF-IDF baseline
  -> fine-tuned DistilBERT
  -> validation-only abstention threshold
  -> saved local artifact
  -> evaluation report
  -> FastAPI accept/abstain response
  -> focused tests and honest README
```

Removing any item above would weaken the central claim. Adding another model,
dataset, service, interface, or UI would expand rather than complete it.

## Assumptions requiring early validation

| Assumption | Validate by | Failure response |
|---|---:|---|
| BANKING77 pinned loader and 77-label mapping work | Hour 2 | Fix source/revision; no substitute dataset without scope change |
| PyTorch detects intended device | Hour 1 | Continue CPU baseline; time-box GPU repair |
| DistilBERT forward pass fits memory | Hour 3 | Reduce batch, not architecture |
| Training fits Hour 6–9 | Hour 8 | One epoch; then documented frozen-embedding fallback |
| Saved artifact loads in a new process | Hour 9 | Block API work until fixed |
| Threshold selector never accesses test labels | Before Hour 11 | Fail evaluation; do not bypass |

## Strict scope freeze

Scope freezes when `make baseline` produces a reloadable artifact and valid
test report, no later than Hour 6.

After freeze:

- model, dataset and interface choices cannot change silently;
- new dependencies require justification;
- new features enter the parking lot;
- only defects blocking acceptance criteria may displace time.

No blocking architecture question remains. The specification therefore makes
and labels assumptions rather than pausing for non-material preferences.

