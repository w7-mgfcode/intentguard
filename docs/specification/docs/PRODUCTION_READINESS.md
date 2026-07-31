# Proportional Production Readiness

## Included

### Configuration

- `configs/default.toml` is the tracked default.
- Environment variables may override artifact directory, device, log level, and
  host/port.
- Training parameters are recorded in the artifact.
- Dataset/model identifiers and revisions are explicit.

No secret is required. `.env.example` documents optional overrides only.

The tracked TOML should remain small:

```toml
[project]
seed = 42

[data]
dataset_id = "PolyAI/banking77"
dataset_revision = "<verified-before-implementation>"
validation_fraction = 0.15

[model]
base_model_id = "distilbert/distilbert-base-uncased"
base_model_revision = "<verified-before-implementation>"
max_length = 96
epochs = 2
train_batch_size = 16
eval_batch_size = 32
learning_rate = 2e-5
weight_decay = 0.01

[threshold]
minimum_coverage = 0.70

[runtime]
device = "auto"
artifact_root = "artifacts"

[logging]
level = "INFO"
```

Placeholders must be replaced with verified immutable revisions before the
first report intended for publication.

### Structured logging

Required event types:

- `service_start`;
- `artifact_loaded`;
- `prediction_completed`;
- `prediction_rejected`;
- `prediction_failed`;
- `evaluation_started`;
- `evaluation_completed`.

Prediction logs include:

- timestamp;
- level and event;
- request ID;
- input character length;
- decision;
- predicted intent when accepted;
- confidence;
- tokenizer truncation status;
- model version;
- latency;
- error category where applicable.

Raw request text is excluded from INFO logs.

### Input validation

Pydantic validates:

- required `text`;
- trimmed length `1..512`;
- no unknown fields;
- optional request ID format;
- response probability range and valid decision/intent combination.

### Health check

`GET /health` confirms:

- model and tokenizer are loaded;
- label mapping contains 77 unique labels;
- threshold is within `[0,1]`;
- model label count matches metadata;
- artifact manifest is readable.

It does not call external services.

### Error handling

Domain exceptions are defined for:

- invalid configuration;
- dataset contract failure;
- artifact corruption;
- model load failure;
- prediction failure;
- evaluation incompatibility.

Only the API module translates domain exceptions to HTTP responses.

### Reproducibility

- Locked dependencies.
- Recorded seeds and revisions.
- Saved configurations and label maps.
- Evaluation from reloaded artifacts.
- Documented non-determinism limitations.

### Basic CI

CI runs on CPU and shall:

1. install from the lockfile;
2. run Ruff;
3. run mypy over `src/intentguard`;
4. run unit and contract tests;
5. run an API test using a tiny deterministic predictor fixture;
6. optionally run a tiny CPU training smoke test if total CI time remains
   reasonable.

CI does not download or fine-tune the full transformer.

### Latency measurement

The evaluation command:

- warms up the model;
- measures repeated single-item predictions;
- reports p50/p95;
- records device and precision;
- excludes model loading from steady-state inference latency;
- reports startup time separately if measured.

## Dependency locking

Use `uv` with:

- a declared lower/upper compatibility range in `pyproject.toml`;
- a committed `uv.lock`;
- lockfile-based CI installation;
- dependency revision in provenance output.

The implementation should avoid prematurely pinning a CUDA wheel URL into
portable project metadata. The README must document the tested PyTorch/CUDA
installation path after it is actually validated.

## Packaging decision

The guaranteed MVP uses a local `uv` environment and Makefile. Docker is
post-weekend because:

- GPU pass-through differs across Linux and WSL;
- model weights should not be copied into an image;
- the project has one local process;
- the lockfile already provides the important reproducibility signal;
- Docker work would displace model evaluation and testing.

## Limitations documentation

The final repository must include:

- dataset scope and licence;
- taxonomy limitations;
- confidence and abstention limitations;
- unsupported-query fixture limitations;
- measured hardware and software environment;
- no production usage or business-impact claims;
- security and privacy note for logs;
- known failure examples.

## Explicit exclusions

The following are not “missing production readiness.” They are disproportional
to this MVP:

- distributed tracing;
- Prometheus/Grafana;
- Kubernetes;
- message broker;
- database;
- model registry;
- feature store;
- online drift service;
- cloud deployment;
- load-testing platform;
- authentication and rate limiting.

They may be discussed as scenario-dependent future work, not listed as automatic
next steps.
