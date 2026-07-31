# ADR-0004: `uv` environment and local artifacts; no weekend Docker

- **Status:** Accepted
- **Date:** 2026-07-31

## Context

The system must reproduce locally on Linux or WSL without paid infrastructure.
The user has Docker capability, but GPU container setup, image size and artifact
distribution could consume time that should be spent on evaluation and tests.

## Decision

- Use Python 3.11.
- Declare dependencies in `pyproject.toml`.
- Commit `uv.lock`.
- Use a Makefile as the documented command layer.
- Store generated model artifacts in a gitignored local directory.
- Run CI on CPU using the lockfile and tiny fixtures.
- Exclude Docker from guaranteed MVP.

## Alternatives considered

### `requirements.txt` and virtualenv

Simple, but weaker lock resolution and grouped development dependencies.

### Poetry

Valid, but adds no advantage over the selected lightweight workflow.

### Dockerfile

Useful for deployment, but GPU pass-through and model-weight handling increase
weekend risk. A CPU inference image would not validate the target training
path.

### Docker Compose

No second service exists, so Compose would be decorative.

### Model registry or object storage

Unnecessary for one local artifact.

## Consequences

### Positive

- Fast setup and committed dependency resolution.
- Native access to the local NVIDIA stack.
- Simple clean-environment CI.
- No image build or registry dependency.

### Negative

- Host CUDA/PyTorch compatibility remains an installation concern.
- Reproduction across operating systems is not as isolated as a validated
  container.
- Model artifacts must be produced locally or deliberately published later.

## Reconsideration trigger

Reconsider after the MVP when:

- all MUST evaluation and tests pass;
- a deployment target is known;
- a repeatable CPU or NVIDIA container can be validated without embedding model
  weights or secrets;
- an interviewer or employer specifically requests container packaging.

