# AGENTS.md

## Mission

Implement the smallest complete IntentGuard weekend MVP described in this
repository. The objective is a credible, locally reproducible production-ML
portfolio project—not a broad platform.

## Source-of-truth order

1. `docs/REQUIREMENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/ML_SYSTEM_DESIGN.md`
4. `docs/INTERFACE_CONTRACT.md`
5. `docs/TEST_STRATEGY.md`
6. Accepted ADRs under `docs/adr/`
7. `docs/IMPLEMENTATION_PLAN.md`

If documents conflict, requirements and accepted ADRs win. Report the conflict
before making a change that alters behavior.

## Architecture boundaries

- Use one modular Python process.
- Use BANKING77 as the only primary dataset.
- Implement one classical baseline: TF-IDF plus logistic regression.
- Implement one improved model: `distilbert-base-uncased` fine-tuned for
  77-class classification.
- Expose one public inference interface through FastAPI.
- Store artifacts in the local filesystem.
- Keep reusable logic in `src/intentguard/`, never solely in notebooks.
- Treat the unsupported-query fixture as a behavioral test fixture, not a
  benchmark proving general out-of-domain detection.

## Approved dependencies

The initial approved dependency families are:

- Python 3.11
- PyTorch
- Hugging Face `transformers` and `datasets`
- scikit-learn
- FastAPI, Uvicorn, and Pydantic
- NumPy and pandas only where needed
- pytest, pytest-cov only for local diagnostic use, Ruff, and mypy
- `uv` for dependency locking and task environment management

Do not add a dependency when the Python standard library or an approved
dependency already provides the required behavior.

## Forbidden overengineering

Do not add:

- a frontend;
- a database, vector store, cache, queue, or message broker;
- MLflow, Weights & Biases, Prometheus, OpenTelemetry, or distributed tracing;
- Docker or cloud deployment during MUST work;
- multiple transformers, ensembles, LLMs, RAG, or generative explanations;
- hyperparameter-search frameworks;
- authentication, user accounts, persistence, or ticket-system integration;
- multi-agent runtime logic;
- a second inference interface;
- general OOD-detection claims based on the small behavioral fixture.

If a task requires one of these, stop and mark it `POST-WEEKEND`.

## Working method

Before editing:

1. Inspect the existing code and relevant source-of-truth documents.
2. Identify the requirement and acceptance-criterion IDs affected.
3. Confirm that the task is `MUST`, or explicitly report that it is not.

While editing:

1. Make the smallest reviewable change.
2. Preserve module boundaries and typed contracts.
3. Keep training, inference, and evaluation logic in Python modules.
4. Keep configuration external to code where it affects experiments or
   runtime behavior.
5. Do not silently change dataset splits, seeds, label mappings, thresholds, or
   metric definitions.

After editing:

1. Run the closest focused tests.
2. Run formatting and static checks for touched files.
3. Run the relevant smoke or evaluation command when practical.
4. Update requirement-to-test traceability and documentation when behavior
   changes.

## Planned commands

```bash
make setup       # install locked dependencies
make data        # download, validate, and record BANKING77 metadata
make baseline    # train and evaluate TF-IDF logistic regression
make train       # fine-tune DistilBERT
make evaluate    # create baseline/model/abstention comparison artifacts
make test        # unit, contract, integration, and CPU smoke tests
make lint        # Ruff and mypy
make serve       # run the local API
make demo        # health check plus one accepted and one abstained request
```

Do not report a command as passing unless it was run and its exit status and
relevant output were inspected.

## Dependency-change rules

- Explain why the dependency is necessary.
- Confirm no approved dependency already covers the need.
- Update `pyproject.toml` and `uv.lock` together.
- Run the focused test suite after changing the lockfile.
- New model, storage, serving, observability, or orchestration dependencies
  require an ADR and are outside the frozen weekend scope by default.

## Coding conventions

- Type public functions and Pydantic boundaries.
- Use small modules with explicit responsibilities.
- Prefer pure functions for preprocessing, metrics, and threshold selection.
- Use `pathlib.Path`, not manually concatenated paths.
- Use deterministic ordering when serializing labels or results.
- Never log raw input text at INFO level.
- Raise domain-specific exceptions and translate them once at the API boundary.
- Use structured JSON-compatible log fields.
- Keep constants in configuration or one named constants module.

## Required validation

Every functional change must have the nearest relevant validation:

- data changes: data-contract tests;
- preprocessing changes: unit tests and stable-label test;
- training changes: tiny CPU training smoke test;
- metric changes: hand-calculated fixture test;
- API changes: integration test;
- artifact changes: save/load parity test;
- threshold changes: risk/coverage and boundary tests.

Coverage percentage is not the definition of quality. Critical behavior and
requirement traceability are.

## Definition of done

A task is done only when:

- its acceptance criteria pass;
- relevant tests and validation commands pass;
- generated outputs are inspected;
- documentation and traceability are current;
- no fabricated metric or result appears;
- implementation status is reported honestly.

## Ambiguity handling

- For a reversible, non-architectural uncertainty, make the smallest reasonable
  assumption and record it.
- For a choice affecting dataset, model, interface, dependencies, metric
  meaning, or scope, stop and request a decision.
- Never redesign the project to solve an ambiguity.

## Status vocabulary

Use these exact meanings:

- **Implemented:** code exists and relevant validation passed.
- **Mocked:** behavior is simulated and not the real integration.
- **Partial:** some acceptance criteria remain unmet.
- **Planned:** documentation exists but implementation does not.
- **Blocked:** progress requires a decision, resource, or failed prerequisite.

Never blur these states.

## Weekend stop rule

Stop and report instead of expanding the project when:

- the requested work is outside MUST scope;
- the change introduces a second model, service, dataset, or interface;
- the task would threaten the Sunday completion gate;
- model training or data preparation exceeds its time box;
- a test or metric cannot be made honest and reproducible.

