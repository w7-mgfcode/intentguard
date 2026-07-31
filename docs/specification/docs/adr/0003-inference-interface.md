# ADR-0003: One FastAPI inference interface

- **Status:** Accepted
- **Date:** 2026-07-31

## Context

The project needs a small but genuine inference boundary demonstrating typed
validation, model loading, health behavior, error handling and latency. It must
remain easy to run in an interview.

## Decision

Expose:

- `GET /health`
- `POST /v1/predict`

Use FastAPI and Pydantic. Treat abstention as a successful HTTP 200 model
decision. Training and evaluation remain operator commands; no second inference
CLI is added.

## Alternatives considered

### CLI only

Simplest implementation, but shows less boundary validation and is less
representative of how a model becomes part of a system.

### CLI plus FastAPI

Convenient but duplicates inference presentation and testing. Training/eval
commands already provide sufficient CLI operation.

### Gradio or Streamlit

More visual, but a frontend would consume time without improving evaluation or
engineering evidence.

### Multiple services

Unjustified for one model and one local process.

## Consequences

### Positive

- Typed, inspectable contract.
- Clear accept versus abstain semantics.
- Easy curl-based interview demo.
- Health and artifact consistency can be tested.
- Inference remains separate from training.

### Negative

- Adds web-framework dependencies.
- Does not demonstrate batch throughput or asynchronous processing.
- Local API is not a claim of production scalability or security.

## Reconsideration trigger

Reconsider if:

- API implementation threatens the Sunday Hour 13 gate;
- the target environment explicitly prohibits HTTP serving;
- a later consumer requires batch-file inference or a specific protocol.

A future batch interface must reuse the predictor module and receive its own
requirements; it must not alter the weekend endpoint contract silently.

