# Project Brief

## Purpose

IntentGuard classifies short English banking-support requests into one of the
77 BANKING77 intents. When confidence is insufficient, it returns `abstain`
instead of forcing a route.

## Target user

The immediate user is a support-platform engineer evaluating whether an
automated intent-routing component is accurate, measurable, and safe enough to
place before a human support queue.

The portfolio audience is a Senior AI Solutions Engineer, Senior AI Developer,
Data Scientist, or Production ML interviewer.

## Problem statement

A normal classifier always emits a class, even for ambiguous or unsupported
inputs. IntentGuard demonstrates a more production-oriented contract:

1. classify supported in-domain requests;
2. expose confidence and model metadata;
3. abstain below a validation-derived threshold;
4. measure quality, calibration, coverage, and latency;
5. document where the behavior is not trustworthy.

## Portfolio objective

Demonstrate that the developer can move an NLP model beyond a notebook into a
tested, reproducible, locally served ML system while making deliberate scope
tradeoffs.

## Job-relevance mapping

| Employer signal | Repository evidence |
|---|---|
| Python engineering | Modular package, typed API, configuration, tests |
| PyTorch | DistilBERT fine-tuning and local inference |
| Hugging Face | Pinned dataset and model revisions |
| Production AI | Artifacts, validation, error handling, health check |
| Evaluation | Baseline comparison, macro-F1, calibration, risk/coverage |
| Responsible implementation | Abstention, privacy-conscious logs, limitations |
| Deployment judgment | Local API and lockfile; no decorative infrastructure |
| Communication | Two-minute README and five-minute demo |

## Measurable definition of success

### Engineering success — required

- The documented setup works on a clean compatible environment.
- BANKING77 is downloaded and validated reproducibly.
- The baseline and transformer are evaluated on the same untouched test split.
- Evaluation produces machine-readable JSON and a human-readable comparison.
- The API loads a versioned local artifact and validates inputs.
- Critical tests and one end-to-end smoke test pass.
- Latency is measured on the local device used for the report.
- The README reports real results or explicitly says they are not measured.

### Model hypothesis — tested, not guaranteed

- The transformer is expected to improve test macro-F1 over the baseline.
- The abstention policy is expected to lower error among accepted predictions
  relative to accepting every prediction.

If either hypothesis is false, the project remains an honest engineering
deliverable. The negative result and error analysis must be documented; the
repository must not claim an improvement.

## Constraints

- 12–16 focused implementation hours.
- One developer using coding agents.
- Local execution on RTX 5060 Mobile, 24 GB RAM, Intel i7-13650HX.
- CPU-compatible inference and CPU-sized automated tests.
- No paid APIs or managed services.
- One primary dataset, baseline, improved model, API, evaluation pipeline, and
  local execution path.

## Non-goals

- General chatbot or generative support agent.
- Production ticket-system integration.
- Multilingual or multi-domain classification.
- Universal OOD detection.
- Online learning, feedback capture, or active learning.
- User interface.
- Cloud deployment, Kubernetes, streaming, model registry, or monitoring stack.
- Business impact, cost saving, or real-user claims.

## Weekend completion boundary

The weekend is complete when the engineering-success criteria pass and a
five-minute local demonstration can:

1. show the baseline-versus-transformer evaluation report;
2. start the API;
3. return a normal classified request;
4. return a validated abstention response;
5. explain one measured limitation.

Everything else moves to the feature parking lot.

## Assumptions

- **A-001:** Python 3.11 and a compatible NVIDIA/PyTorch environment are
  available.
- **A-002:** The BANKING77 dataset can be downloaded during setup and is used
  under CC BY 4.0 with attribution.
- **A-003:** `distilbert-base-uncased` fits the target GPU at sequence length 96
  with an adjusted batch size.
- **A-004:** English support requests fit within 512 Unicode characters for the
  demonstration contract.
- **A-005:** Local filesystem artifacts are sufficient; concurrent model
  training and serving are not required.

## Early validation assumptions

Validate these before Hour 3:

1. dataset loader returns the expected train/test schema and 77 labels;
2. model and tokenizer revisions resolve;
3. CUDA is visible if GPU training is intended;
4. a single forward pass fits memory;
5. the API can load a minimal placeholder artifact contract.

