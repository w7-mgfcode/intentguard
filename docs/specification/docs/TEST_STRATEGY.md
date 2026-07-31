# Test and Evaluation Strategy

## Principle

Tests protect contracts that would make evaluation or serving misleading if
they broke. The project does not optimize for a coverage percentage.

## Test layers

### Unit tests

| Test target | Critical cases | Traceability |
|---|---|---|
| Preprocessing | trim behavior, empty text, stable normalization | FR-001, NFR-004, AC-001 |
| Label mapping | 77 unique labels, deterministic order, round trip | FR-001, FR-008, AC-001, AC-010 |
| Metrics | hand-calculated macro-F1, accuracy, ECE, coverage, selective risk | FR-005, AC-004, AC-011 |
| Threshold selection | minimum coverage, lowest risk, ties, exact-boundary confidence | FR-004, AC-005, AC-006, AC-007 |
| Artifact validation | missing files, bad threshold, label mismatch, manifest mismatch | FR-008, AC-009, AC-010 |
| Response construction | valid accept/abstain invariants | FR-006, AC-006, AC-007 |

### Data-contract tests

- A tiny valid canonical dataset passes.
- Missing `text` or `label` fails.
- Unknown label ID/name fails.
- Duplicate example IDs fail.
- Split overlap fails.
- Test split cannot be used by the threshold selector.
- Upstream loader metadata includes dataset source and revision.

Traceability: FR-001, NFR-003, AC-001, AC-005.

### Evaluation regression tests

A committed fixture contains:

- known labels;
- baseline predictions;
- transformer-style probability vectors;
- a minimum-coverage setting;
- hand-checked expected metrics and selected threshold.

The test asserts semantic outputs, not formatted text. Updating expected values
requires explaining the metric-definition change in the pull request and
updating the relevant documentation.

Traceability: FR-004, FR-005, AC-004, AC-005, AC-011.

### Artifact save/load parity test

Use a tiny fitted fixture:

1. produce predictions;
2. save model metadata and artifact;
3. create a new predictor instance;
4. reload;
5. predict the same examples;
6. compare labels and probabilities within documented tolerance.

Traceability: FR-008, NFR-009, AC-010.

### API integration tests

Use a deterministic fake predictor behind the real FastAPI boundary for:

- accepted prediction;
- abstained prediction;
- empty text;
- text of 513 characters;
- malformed JSON;
- extra field;
- model-not-ready health response;
- prediction failure translation;
- raw-text absence from INFO log capture.

These tests validate the interface, not transformer quality.

Traceability: FR-006, FR-007, NFR-004, NFR-005, AC-006–AC-009.

### End-to-end smoke tests

Two smoke paths are required:

1. **CPU CI smoke:** tiny fixture → tiny model/baseline artifact → application
   load → one prediction.
2. **Local full smoke:** saved weekend transformer artifact → application load
   → health → accepted and abstained example.

The local full smoke is not required in remote CPU CI because downloading and
loading the complete artifact would make CI slow and fragile.

Traceability: FR-003, FR-006–FR-010, AC-003, AC-013, AC-014.

### Reproducibility check

- Run baseline training twice with the same seed and fixture.
- Assert identical label predictions and metrics.
- Run threshold selection twice and assert exact output.
- For transformer training, record two-run comparison only if time permits.
  Exact cross-hardware equality is not an acceptance criterion.

Traceability: NFR-003, AC-002, AC-005, AC-011.

## Evaluation protocol

1. Freeze dataset/model revisions and configuration.
2. Run `make data`.
3. Run `make baseline`.
4. Run `make train`.
5. Reload saved artifacts.
6. Run `make evaluate`.
7. Inspect JSON and Markdown outputs.
8. Run `make test`.
9. Record the tested hardware and software environment.
10. Copy only generated metrics into the final README.

## Output files

```text
reports/<run_id>/
├── comparison.json
├── comparison.md
├── classification_per_class.csv
├── confusion_pairs.csv
├── risk_coverage.csv
├── unsupported_fixture.json
├── latency.json
└── environment.json
```

Every report contains or references:

- run ID;
- artifact IDs;
- dataset/model revisions;
- test example hash;
- configuration hash;
- creation timestamp.

## Validation commands

```bash
make lint
make test
make evaluate
make demo
```

Expected behavior:

- commands return non-zero on contract or evaluation incompatibility;
- test output identifies the failing contract;
- evaluation output points to machine-readable and human-readable reports;
- demo output shows transport success independently of model correctness.

## What is not tested in the MVP

- horizontal scaling;
- concurrent load;
- adversarial security;
- multilingual inputs;
- real support-ticket distributions;
- business-routing correctness;
- general OOD performance;
- online drift;
- cloud or container deployment.

