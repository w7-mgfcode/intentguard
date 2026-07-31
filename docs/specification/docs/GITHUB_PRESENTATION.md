# GitHub Presentation

## Recruiter two-minute path

A recruiter should see, in this order:

1. one-sentence problem and portfolio purpose;
2. honest implementation status;
3. measured baseline-versus-transformer table;
4. one architecture diagram;
5. quick-start and one API example;
6. tests and reproducibility evidence;
7. limitations and non-goals.

## Suggested repository description

> Local-first, confidence-aware banking intent classifier comparing TF-IDF with
> a fine-tuned DistilBERT model through reproducible evaluation and a tested
> FastAPI boundary.

## Suggested topics

```text
python
pytorch
huggingface
transformers
fastapi
machine-learning
nlp
intent-classification
model-evaluation
selective-prediction
mlops
production-ml
```

Avoid `production-ready` unless the README carefully qualifies the environment
and limitations.

## Final README structure

1. Title and one-sentence outcome.
2. Honest status badge/table.
3. Why this project exists.
4. What is implemented.
5. Results.
6. Architecture.
7. Quick start.
8. API example.
9. Evaluation methodology.
10. Tests and reproducibility.
11. Limitations.
12. Repository structure.
13. Decisions and post-weekend parking lot.
14. Dataset/model attribution and licence.

## Quick start

The implementation README should prefer:

```bash
git clone <repository-url>
cd intentguard
make setup
make data baseline train evaluate test
make serve
```

If transformer training is too long for a recruiter, document a second demo
path that downloads a release artifact only after an artifact has actually been
published. Do not include a dead or planned download command.

## Sample input and output

Input:

```json
{"text":"How do I activate my new card?"}
```

Output schema:

```json
{
  "request_id": "req_...",
  "decision": "accept",
  "intent": "activate_my_card",
  "confidence": "<measured per request>",
  "threshold": "<selected from validation>",
  "input_truncated": "<true when tokens were removed>",
  "model_version": "<artifact version>",
  "latency_ms": "<measured locally>"
}
```

## Evaluation table template

Replace every placeholder from generated reports. Never estimate these values.

| Model | Test macro-F1 | Accuracy | ECE | p50 latency | p95 latency |
|---|---:|---:|---:|---:|---:|
| TF-IDF + logistic regression | Not measured | Not measured | Not measured | Not measured | Not measured |
| Fine-tuned DistilBERT | Not measured | Not measured | Not measured | Not measured | Not measured |

Selective-prediction table:

| Threshold source | Coverage | Accepted accuracy | Selective risk | Abstention rate |
|---|---:|---:|---:|---:|
| Validation-only policy | Not measured | Not measured | Not measured | Not measured |

## Implemented versus planned status

Use:

| Capability | Implemented | Measured | Notes |
|---|:---:|:---:|---|
| Validated BANKING77 pipeline | ☐ | ☐ | |
| TF-IDF baseline | ☐ | ☐ | |
| Fine-tuned DistilBERT | ☐ | ☐ | |
| Validation-only threshold | ☐ | ☐ | |
| FastAPI inference | ☐ | ☐ | |
| CPU test suite | ☐ | ☐ | |
| Docker | No | No | Post-weekend only |
| Cloud deployment | No | No | Not required |

## Concise architecture explanation

> Offline commands prepare BANKING77, train a lexical baseline and one
> DistilBERT classifier, select an abstention threshold using validation data,
> and save a local versioned artifact. A single FastAPI process loads that
> artifact and returns either an accepted intent or an abstention. Evaluation
> reloads saved artifacts and compares both models on the untouched test split.

## Limitations block

The first screenful or two should state:

- English banking taxonomy only;
- confidence is not certainty;
- unsupported-query fixture is curated, not a general OOD benchmark;
- no real users, production traffic, or business-impact measurement;
- latency applies only to the documented local environment;
- one global threshold may not treat every intent equally.

## Five-minute interview demonstration

### 0:00–0:40 — Problem and scope

> “This is a deliberately weekend-sized production ML project. It classifies
> fine-grained banking-support intents, compares a lexical baseline with
> DistilBERT, and abstains on low-confidence requests. It does not pretend to be
> a complete support platform.”

Show the status and non-goals.

### 0:40–1:30 — Architecture

Show the compact diagram and explain:

- upstream test isolation;
- shared evaluation pipeline;
- local artifact;
- one serving process.

### 1:30–2:30 — Evaluation

Open the generated comparison table:

- identify the baseline;
- explain macro-F1;
- show whether the transformer actually improved;
- show risk/coverage and the validation-only threshold;
- mention one failure class.

### 2:30–3:40 — Live API

Run:

```bash
make serve
curl -s http://127.0.0.1:8000/health
curl -s -H 'Content-Type: application/json' \
  -d '{"text":"How do I activate my new card?"}' \
  http://127.0.0.1:8000/v1/predict
```

Then run the prepared abstention example through `make demo`.

### 3:40–4:30 — Engineering evidence

Show:

- saved provenance;
- label/threshold consistency checks;
- requirement-to-test traceability;
- one metric regression test;
- privacy-conscious log fields.

### 4:30–5:00 — Limitations and decision quality

> “The abstention fixture does not prove general OOD performance. I excluded a
> frontend, database, Docker, cloud deployment and monitoring stack because
> they would not improve the core weekend evidence. The next meaningful study
> would be stronger OOD data or per-class threshold analysis—not more
> infrastructure.”
