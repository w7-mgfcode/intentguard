# Primary requirement traceability

Canonical hierarchy: `M1` milestone → `W01`–`W03` umbrellas → `E01`–`E08` epics → `S01.1`–`S08.3` subtasks. Legacy `U##`/`C##.#` identifiers remain aliases only. Each identifier below has exactly one primary row; secondary relationships are listed separately.

## Source tasks

| ID | Umbrella | Epic | Subtask | Legacy aliases | Implementation path | Validation command | Expected evidence |
|---|---|---|---|---|---|---|---|
| T-001 | W01 | E01 | S01.1 | U01 / C01.1 | `AGENTS.md` | `make lint && make test` | Locked validated repository skeleton |
| T-002 | W01 | E02 | S02.1 | U02 / C02.1 | `src/intentguard/data.py` | `make data` | Pinned dataset provenance and validated splits |
| T-003 | W02 | E03 | S03.1 | U03 / C03.1 | `src/intentguard/baseline.py` | `make baseline` | Reproducible fitted baseline and report |
| T-004 | W02 | E04 | S04.1 | U04 / C04.1 | `src/intentguard/training.py` | `make train` | Immutable transformer artifact with threshold |
| T-005 | W02 | E05 | S05.1 | U05 / C05.1 | `src/intentguard/evaluation.py` | `make evaluate` | Comparable test and selective-prediction report |
| T-006 | W03 | E06 | S06.1 | U06 / C06.1 | `src/intentguard/api.py` | `make serve then make demo` | Typed real-artifact API evidence |
| T-007 | W03 | E07 | S07.1 | U07 / C07.1 | `scripts/validate_acceptance.py` | `make lint && make test` | CPU validation and acceptance summary |
| T-008 | W03 | E08 | S08.1 | U08 / C08.1 | `README.md` | `uv run python scripts/validate_foundation.py` | Honest recruiter-ready delivery bundle |

## Functional requirements

| ID | Umbrella | Epic | Subtask | Legacy aliases | Implementation path | Validation command | Expected evidence |
|---|---|---|---|---|---|---|---|
| FR-001 | W01 | E02 | S02.2 | U02 / C02.2 | `src/intentguard/data.py` | `make data` | Canonical split sizes label mapping and revision metadata |
| FR-002 | W02 | E03 | S03.1 | U03 / C03.1 | `src/intentguard/baseline.py` | `make baseline` | TF-IDF logistic-regression metrics |
| FR-003 | W02 | E04 | S04.2 | U04 / C04.2 | `src/intentguard/training.py` | `make train` | Fine-tuned 77-class DistilBERT artifact |
| FR-004 | W02 | E04 | S04.3 | U04 / C04.3 | `src/intentguard/threshold.py` | `make train` | Validation-selected persisted threshold |
| FR-005 | W02 | E05 | S05.1 | U05 / C05.1 | `src/intentguard/evaluation.py` | `make evaluate` | Accuracy macro-F1 and baseline comparison |
| FR-006 | W03 | E06 | S06.2 | U06 / C06.2 | `src/intentguard/api.py` | `uv run pytest tests/integration/test_api.py -q` | Typed predict response with accept or abstain status |
| FR-007 | W03 | E06 | S06.2 | U06 / C06.2 | `src/intentguard/api.py` | `uv run pytest tests/integration/test_api.py -q` | Health response with readiness state |
| FR-008 | W02 | E04 | S04.3 | U04 / C04.3 | `src/intentguard/artifacts.py` | `uv run pytest tests/unit/test_artifacts.py -q` | Reloadable immutable metadata and weights |
| FR-009 | W02 | E05 | S05.3 | U05 / C05.3 | `tests/fixtures/unsupported_requests.jsonl` | `make evaluate` | Separate unsupported-request abstention report |
| FR-010 | W01 | E01 | S01.3 | U01 / C01.3 | `Makefile` | `make help` | Complete reproducible command surface |

## Non-functional requirements

| ID | Umbrella | Epic | Subtask | Legacy aliases | Implementation path | Validation command | Expected evidence |
|---|---|---|---|---|---|---|---|
| NFR-001 | W02 | E04 | S04.2 | U04 / C04.2 | `src/intentguard/training.py` | `uv run pytest tests/integration/test_training_smoke.py -q` | Seeded reproducible training smoke evidence |
| NFR-002 | W03 | E07 | S07.1 | U07 / C07.1 | `.github/workflows/ci.yml` | `make test` | Passing CPU suite without GPU requirement |
| NFR-003 | W01 | E01 | S01.2 | U01 / C01.2 | `uv.lock` | `uv lock --check && make setup` | Reproducible locked environment |
| NFR-004 | W03 | E06 | S06.1 | U06 / C06.1 | `src/intentguard/schemas.py` | `uv run pytest tests/contract/test_api_contract.py -q` | Deterministic validation and error bodies |
| NFR-005 | W03 | E06 | S06.1 | U06 / C06.1 | `src/intentguard/logging.py` | `uv run pytest tests/unit/test_logging.py -q` | Sanitized structured log capture |
| NFR-006 | W02 | E05 | S05.2 | U05 / C05.2 | `src/intentguard/evaluation.py` | `make evaluate` | Declared latency distribution and environment |
| NFR-007 | W01 | E01 | S01.1 | U01 / C01.1 | `AGENTS.md` | `make lint` | Ruff mypy and boundary validation |
| NFR-008 | W01 | E01 | S01.2 | U01 / C01.2 | `configs/default.toml` | `uv run pytest tests/unit/test_artifacts.py -q` | Dataset model and dependency provenance fields |
| NFR-009 | W03 | E07 | S07.1 | U07 / C07.1 | `scripts/validate_acceptance.py` | `make lint && make test` | Repeated CPU checks with stable contracts |
| NFR-010 | W03 | E08 | S08.2 | U08 / C08.2 | `docs/OPERATIONS.md` | `uv run python scripts/validate_foundation.py` | Operating fallback and limitation documentation |

## Acceptance criteria

| ID | Umbrella | Epic | Subtask | Legacy aliases | Implementation path | Validation command | Expected evidence |
|---|---|---|---|---|---|---|---|
| AC-001 | W01 | E02 | S02.3 | U02 / C02.3 | `tests/contract/test_data_contract.py` | `make data && uv run pytest tests/contract/test_data_contract.py -q` | Exact split label and provenance assertions |
| AC-002 | W02 | E03 | S03.3 | U03 / C03.3 | `reports/baseline.json` | `make baseline` | Recorded test accuracy and macro-F1 |
| AC-003 | W02 | E04 | S04.3 | U04 / C04.3 | `src/intentguard/artifacts.py` | `make train && uv run pytest tests/unit/test_artifacts.py -q` | Complete reloadable artifact bundle |
| AC-004 | W02 | E05 | S05.1 | U05 / C05.1 | `reports/evaluate/<run_id>/comparison.json` | `make evaluate` | Both approaches compared on the same test IDs, with a negative result reported honestly |
| AC-005 | W02 | E04 | S04.3 | U04 / C04.3 | `src/intentguard/threshold.py` | `uv run pytest tests/unit/test_threshold.py -q` | Proof threshold used validation labels only |
| AC-006 | W03 | E06 | S06.2 | U06 / C06.2 | `tests/integration/test_api.py` | `uv run pytest tests/integration/test_api.py -q` | Accepted request contract |
| AC-007 | W03 | E06 | S06.2 | U06 / C06.2 | `tests/integration/test_api.py` | `uv run pytest tests/integration/test_api.py -q` | Abstained request contract |
| AC-008 | W03 | E06 | S06.1 | U06 / C06.1 | `tests/contract/test_api_contract.py` | `uv run pytest tests/contract/test_api_contract.py -q` | Stable 4xx response evidence |
| AC-009 | W03 | E06 | S06.2 | U06 / C06.2 | `tests/integration/test_api.py` | `uv run pytest tests/integration/test_api.py -q` | Ready and not-ready artifact state |
| AC-010 | W02 | E04 | S04.3 | U04 / C04.3 | `tests/unit/test_artifacts.py` | `uv run pytest tests/unit/test_artifacts.py -q` | Prediction and metadata parity after reload |
| AC-011 | W02 | E05 | S05.1 | U05 / C05.1 | `tests/unit/test_eval_regression.py` | `uv run pytest tests/unit/test_eval_regression.py -q` | Hand-checked metric and threshold regression fixture results |
| AC-012 | W02 | E05 | S05.3 | U05 / C05.3 | `tests/fixtures/unsupported_requests.jsonl` | `make evaluate` | Separate fixture results with no OOD overclaim |
| AC-013 | W03 | E06 | S06.3 | U06 / C06.3 | `scripts/demo.py` | `make demo` | Five-minute demo output from loaded transformer artifact |
| AC-014 | W03 | E07 | S07.2 | U07 / C07.2 | `reports/acceptance.json` | `make lint && make test && make evaluate && make demo` | All MUST Implemented and applicable claims Measured |

## Secondary relationships

| Identifier | Secondary owner | Legacy alias | Meaning |
|---|---|---|---|
| AC-011 | W02 / E05 / S05.2 | U05 / C05.2 | secondary-evaluation-context |
