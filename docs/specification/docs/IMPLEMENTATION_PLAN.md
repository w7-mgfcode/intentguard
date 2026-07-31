# Weekend Implementation Plan

Only tasks marked **MUST** belong to the guaranteed MVP.

## T-001 — Repository and environment

- **Priority:** MUST
- **Time:** Hour 0–1
- **Objective:** Establish a locked, testable Python project with documented
  commands.
- **Files:** `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`,
  `.env.example`, `configs/default.toml`, package/test `__init__.py` files,
  `.github/workflows/ci.yml`.
- **Prerequisites:** Python 3.11, `uv`, Git, compatible PyTorch installation.
- **Boundary:** No application features, Docker, pre-commit framework, or
  release automation.
- **Acceptance criteria:** Supports NFR-008 and AC-014; package imports; one
  placeholder test passes.
- **Validation command:** `make setup && make lint && uv run pytest -q`
- **Expected output:** Locked environment, clean static checks, one passing
  smoke test.
- **Stop condition:** If PyTorch/CUDA installation cannot be resolved within
  45 minutes, establish CPU dependencies, record the GPU blocker, and continue
  with data/baseline work.

## T-002 — Data ingestion and validation

- **Priority:** MUST
- **Time:** Hour 1–3
- **Objective:** Produce validated, versioned train/validation/test metadata.
- **Files:** `src/intentguard/config.py`, `src/intentguard/data.py`,
  `src/intentguard/schemas.py`, `scripts/prepare_data.py`,
  `tests/contract/test_data_contract.py`, `configs/default.toml`.
- **Prerequisites:** T-001.
- **Boundary:** BANKING77 only; no augmentation, external OOD dataset, or text
  cleaning beyond explicit validation/canonicalization.
- **Acceptance criteria:** FR-001, NFR-003, AC-001.
- **Validation command:** `make data && uv run pytest tests/contract/test_data_contract.py -q`
- **Expected output:** Validated split metadata with 77 labels, revision,
  counts, hashes, seed, and licence attribution.
- **Stop condition:** If the upstream dataset is unavailable after 45 minutes,
  use a cached verified copy if present. Otherwise switch to the synthetic
  fallback, label the run degraded, and prohibit benchmark claims.

## T-003 — Working baseline first

- **Priority:** MUST
- **Time:** Hour 3–6
- **Objective:** Establish the first complete train-save-reload-evaluate path.
- **Files:** `src/intentguard/baseline.py`, `src/intentguard/metrics.py`,
  `src/intentguard/artifacts.py`, `scripts/train_baseline.py`,
  `tests/unit/test_metrics.py`, `tests/unit/test_baseline.py`.
- **Prerequisites:** T-002.
- **Boundary:** One TF-IDF/logistic pipeline; no feature engineering study or
  hyperparameter search.
- **Acceptance criteria:** FR-002, FR-005, FR-008, AC-002, AC-011.
- **Validation command:** `make baseline && uv run pytest tests/unit/test_metrics.py tests/unit/test_baseline.py -q`
- **Expected output:** Reloadable baseline artifact and real baseline
  evaluation JSON.
- **Stop condition:** **Scope-freeze checkpoint.** Do not start transformer
  work until baseline evaluation is complete. If not complete by Hour 6, fix
  the baseline and cut all SHOULD/STRETCH work.

## T-004 — DistilBERT improved model

- **Priority:** MUST
- **Time:** Hour 6–9
- **Objective:** Fine-tune, save, reload, and validate the single transformer.
- **Files:** `src/intentguard/training.py`,
  `src/intentguard/predictor.py`, `src/intentguard/artifacts.py`,
  `scripts/train_transformer.py`, `tests/unit/test_artifacts.py`,
  `tests/integration/test_training_smoke.py`.
- **Prerequisites:** T-003; successful tokenizer/model forward-pass check.
- **Boundary:** One base checkpoint, initial documented hyperparameters, at
  most one memory-driven batch adjustment.
- **Acceptance criteria:** FR-003, FR-008, NFR-001–NFR-003, AC-003, AC-010.
- **Validation command:** `make train && uv run pytest tests/unit/test_artifacts.py tests/integration/test_training_smoke.py -q`
- **Expected output:** Reloadable transformer bundle with validation
  probabilities and provenance.
- **Stop condition:** If CUDA OOM occurs, retry once with batch size 8. If no
  valid artifact exists by Hour 9, use one epoch. If integration remains
  blocked, replace fine-tuning with frozen DistilBERT embeddings plus logistic
  regression, mark FR-003 partial, and do not claim a fine-tuned model.

## T-005 — Abstention and comparative evaluation

- **Priority:** MUST
- **Time:** Hour 9–11
- **Objective:** Select the validation-only threshold and produce an honest
  baseline/model comparison.
- **Files:** `src/intentguard/threshold.py`,
  `src/intentguard/evaluation.py`, `scripts/evaluate.py`,
  `tests/unit/test_threshold.py`, `tests/unit/test_eval_regression.py`,
  `tests/fixtures/unsupported_requests.jsonl`.
- **Prerequisites:** T-003 and T-004 artifacts.
- **Boundary:** One global threshold; no temperature scaling, per-class
  thresholds, or tuning on test data.
- **Acceptance criteria:** FR-004, FR-005, FR-009, AC-004, AC-005, AC-011,
  AC-012.
- **Validation command:** `make evaluate && uv run pytest tests/unit/test_threshold.py tests/unit/test_eval_regression.py -q`
- **Expected output:** Comparison JSON/Markdown, per-class errors,
  risk/coverage, unsupported-fixture report, and latency metadata.
- **Stop condition:** If any artifact references different test IDs, label
  maps, or dataset revisions, stop. Never force the comparison.

## T-006 — API and integration

- **Priority:** MUST
- **Time:** Hour 11–13
- **Objective:** Serve the frozen transformer bundle through the typed
  inference contract.
- **Files:** `src/intentguard/api.py`, `src/intentguard/errors.py`,
  `src/intentguard/logging.py`, `src/intentguard/schemas.py`,
  `tests/integration/test_api.py`, `scripts/demo.py`.
- **Prerequisites:** T-004 and T-005.
- **Boundary:** `GET /health` and `POST /v1/predict` only; no CLI inference,
  persistence, authentication, batching, or frontend.
- **Acceptance criteria:** FR-006–FR-008, NFR-004–NFR-006, AC-006–AC-010.
- **Validation command:** `uv run pytest tests/integration/test_api.py -q && make demo`
- **Expected output:** Ready health response plus typed accept and abstain
  behavior without raw-text INFO logs.
- **Stop condition:** **Sunday completion gate.** By Hour 13, a saved artifact
  must load and answer one valid request. If not, stop all presentation work and
  fix only the vertical slice.

## T-007 — Full focused validation

- **Priority:** MUST
- **Time:** Hour 13–14.5
- **Objective:** Run critical validation from a clean process and close
  requirement gaps.
- **Files:** tests and traceability/documentation files affected by failures.
- **Prerequisites:** T-001–T-006.
- **Boundary:** Fix failing requirements only; no refactors for style, coverage
  chasing, or new features.
- **Acceptance criteria:** AC-001–AC-014.
- **Validation command:** `make lint && make test && make evaluate && make demo`
- **Expected output:** All critical checks pass and report paths are inspected.
- **Stop condition:** If a critical requirement fails at Hour 14.5, remove
  incomplete claims and deliver a clearly partial repository rather than hide
  the failure.

## T-008 — Documentation and demo

- **Priority:** MUST
- **Time:** Hour 14.5–16
- **Objective:** Make the repository understandable in two minutes and
  demonstrable in five.
- **Files:** `README.md`, `docs/LIMITATIONS.md`,
  `docs/TRACEABILITY.md`, evaluation table, sample response, repository
  metadata.
- **Prerequisites:** Real outputs from T-005 and passing state from T-007.
- **Boundary:** Document measured results only; no website, video production,
  badges requiring external services, or fabricated screenshots.
- **Acceptance criteria:** NFR-010, AC-012–AC-014.
- **Validation command:** Follow the README from a clean shell; run every
  displayed command; execute the five-minute script.
- **Expected output:** Accurate quick start, result table, status,
  architecture, limitations, and reproducible demo.
- **Stop condition:** At Hour 16, stop. List unfinished items as partial or
  post-weekend.

## Optional backlog

### T-101 — Temperature scaling

- **Priority:** SHOULD
- **Prerequisite:** All MUST work complete before Hour 14.
- **Boundary:** Validation-only temperature fitting and before/after ECE.
- **Stop:** Cut immediately if any MUST documentation or test is incomplete.

### T-102 — Per-class error narrative

- **Priority:** SHOULD
- **Boundary:** Discuss the five largest confusion pairs; no visualization
  framework.

### T-201 — Docker CPU inference image

- **Priority:** STRETCH
- **Boundary:** CPU inference only, artifact mounted at runtime.

### T-301 — Deployment, drift, feedback, multilingual and real integration

- **Priority:** POST-WEEKEND
- **Boundary:** Requires separate requirements, data, risk analysis, and ADRs.

