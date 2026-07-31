# IntentGuard Repository Agent Guide

## Mission

Build the smallest coherent, verifiable IntentGuard Weekend MVP: a confidence-aware BANKING77 intent classifier with one lexical baseline, one fine-tuned DistilBERT model, reproducible evaluation, selective prediction, and one typed FastAPI inference boundary.

Preserve evidence and repository conventions. Do not expand the product into a platform.

## Required startup

Before substantial work:

1. Read `rules/core-rules.md`.
2. Read `rules/safety-and-approval.md`.
3. Select exactly one primary contract from `commands/`.
4. Read this file and the relevant authoritative specification documents.
5. Inspect relevant code, repository state, and any current `.fpat/plan.md` or `.fpat/handoff.md`.

Follow links only when they answer a material question; do not load the entire knowledge base ceremonially.

## FPAT Lite workflow

| Mode | Contract | Purpose |
|---|---|---|
| `prime` | `commands/prime.md` | Read-only baseline |
| `brainstorm` | `commands/brainstorm.md` | Compare realistic options |
| `plan` | `commands/plan.md` | Define a verifiable approach |
| `implement` | `commands/implement.md` | Make one approved local change |
| `validate` | `commands/validate.md` | Produce executed evidence |
| `handoff` | `commands/handoff.md` | Preserve resumable state |

Invoke `$fpat-lite <mode> [task]` in Codex or `/fpat-lite <mode> [task]` in Claude Code.

## Authority

`docs/specification/` is the sole authoritative design source. Do not copy or maintain a second complete specification.

Use this precedence inside that source:

1. `docs/specification/docs/REQUIREMENTS.md`
2. `docs/specification/docs/ARCHITECTURE.md`
3. `docs/specification/docs/ML_SYSTEM_DESIGN.md`
4. `docs/specification/docs/INTERFACE_CONTRACT.md`
5. `docs/specification/docs/TEST_STRATEGY.md`
6. accepted ADRs in `docs/specification/docs/adr/`
7. `docs/specification/docs/IMPLEMENTATION_PLAN.md`

`.fpat/plan.md` records approved execution decisions but does not replace the specification.

## Strict-MVP boundary

Strict MVP requires every MUST capability to be `Implemented` and every applicable dataset, model, and evaluation claim to be `Measured`. A MUST capability reported as `Partial`, `Mocked`, `Blocked`, or `Planned` does not satisfy strict MVP.

The normalized lifecycle is:

1. Load and validate a pinned BANKING77 revision and its canonical splits.
2. Train and measure the TF-IDF logistic-regression baseline.
3. Fine-tune one `distilbert-base-uncased` classifier.
4. During `make train`, generate validation predictions, select the confidence threshold from validation data only, and persist it in an immutable artifact.
5. During `make evaluate`, load that artifact and threshold, evaluate the untouched test split, and write evidence.
6. Load the same artifact at FastAPI startup and serve typed health and prediction responses.
7. Run the strict demo through the real loaded transformer artifact.

Test labels must never influence threshold selection. A deterministic predictor is allowed only for tests or an explicitly labelled degraded mode.

## Approved architecture and dependencies

- Python 3.11 with a `src/` package layout.
- `uv` for locking and environment management; `Makefile` as the primary command interface.
- PyTorch, Transformers, Datasets, NumPy, and scikit-learn for the approved ML path.
- FastAPI, Uvicorn, and Pydantic for the only public inference boundary.
- pytest, pytest-cov, Ruff, and mypy for local validation.
- Local immutable artifacts, JSON reports, and ordinary structured logging.
- CPU GitHub Actions for reproducible validation; GPU claims require separately executed evidence.

Do not add Docker, frontends, databases, MLflow, Prometheus, pre-commit frameworks, cloud SDKs, deployment tooling, additional model families, or unrelated developer tooling. Docker is POST-WEEKEND.

## Status and evidence vocabulary

- `Implemented`: the required behavior exists and applicable checks pass.
- `Measured`: an empirical claim is backed by reproducible output from the declared artifact and data.
- `Partial`: only part of the stated capability exists.
- `Mocked`: a test or degraded substitute exists, but the real capability does not.
- `Blocked`: work cannot proceed within current constraints and the reason is recorded.
- `Planned`: work has an approved design or backlog entry but is not implemented.

Report capability status separately from evidence. Never describe planned, mocked, or synthetic results as implemented or measured. Never invent metrics, revisions, hashes, timings, or hardware compatibility.

## Engineering and validation rules

- Inspect before changing and state material assumptions.
- Define observable acceptance criteria before substantial implementation.
- Prefer the simplest adequate implementation and do not refactor unrelated code.
- Preserve deterministic seeds, stable split and label contracts, typed boundaries, and artifact provenance.
- Use the same preprocessing and label mapping across training, evaluation, and serving.
- Keep training and evaluation offline; serving loads an artifact and does not train.
- Do not overwrite or discard user changes.
- Never claim an unexecuted or unavailable check passed.
- Run the narrowest relevant checks first, then the broader acceptance suite.
- Review the final diff and record limitations, fallbacks, and unresolved evidence honestly.
- Generated data, model artifacts, and reports remain untracked except for their explanatory README files.

## Repository-wide traceability

- Every implementation change must identify the affected T, FR, NFR, and AC identifiers.
- Every identifier must retain exactly one primary umbrella owner and exactly one primary child-issue owner.
- Secondary relationships are allowed, but they must be explicitly labelled secondary and may not replace primary ownership.
- Any ownership change must update both `docs/backlog/TRACEABILITY.md` and `docs/backlog/traceability.json`.
- The Markdown and JSON representations must remain semantically and structurally consistent.
- Validation must fail on missing, duplicated, unknown, or conflicting primary ownership.
- Pull requests must report affected requirement identifiers and the evidence produced by executed validation commands.

Do not copy the complete traceability matrix into repository instructions; link to the maintained backlog sources instead.

## Approval gates and mutation safety

Local and remote mutations are separate:

- Gate A: local repository preparation.
- Gate B: Git initialization and local commit.
- Gate C: remote repository creation and initial push.
- Gate D: GitHub Project, labels, and issue creation.

Obtain explicit approval immediately before entering a gate unless the current request authorizes that exact mutation. Never infer approval for Git or GitHub changes from approval for local files. Do not use mutating `gh` commands during read-only or local-only work.

Avoid destructive operations. Stop and report contradictions, missing authority, secrets, unexpected existing-file conflicts, unsafe ambiguity, or any need to cross the approved gate.

## Weekend scope control

Protect the fixed MUST hierarchy T-001 through T-008. SHOULD, STRETCH, and POST-WEEKEND items are optional and must not block or be presented as completed parts of strict MVP. When a fallback violates a MUST requirement, mark the affected capability accurately and fail the strict-MVP gate.

## Definition of done

A task is done only when the requested behavior exists, applicable checks were actually run, its acceptance criteria were evaluated, the final changes were reviewed, limitations are explicit, and pending work or approval is recorded.
