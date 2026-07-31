# IntentGuard Gate A Plan

## Objective

Prepare the complete local repository foundation and a locally reviewable GitHub backlog for the IntentGuard Weekend MVP. Gate A does not implement the data, baseline, transformer, evaluation, API, or demonstration behavior, and it authorizes no Git or GitHub mutation.

## Authority and fixed decisions

- `docs/specification/` remains the sole authoritative design source.
- The application lives at repository root beside the FPAT Lite workflow files.
- Python 3.11 and `uv` are the reproducibility interface.
- The confidence threshold is selected from validation predictions during `make train`, persisted with the immutable transformer artifact, then loaded and applied to test predictions by `make evaluate`. Test labels never select or tune it.
- Strict MVP requires every MUST capability to be `Implemented` and every applicable dataset, model, and evaluation claim to be `Measured`.
- `Mocked`, `Partial`, `Planned`, or `Blocked` MUST capabilities do not satisfy strict MVP.
- The strict demonstration loads the real transformer artifact. A deterministic predictor is allowed only in tests or explicitly degraded mode.
- Docker is `POST-WEEKEND`.
- The repository license is MIT, as confirmed for Gate A.

## Gate A deliverables

1. Repository-wide governance in `AGENTS.md`, with `CLAUDE.md` delegating to it.
2. Root documentation, Python packaging, locked dependency definition, configuration, Make command contract, minimal package, and foundation-only tests.
3. Generated-directory policies for `data/`, `artifacts/`, and `reports/` while retaining their README files.
4. CPU-only GitHub Actions configuration that runs only foundation checks that exist.
5. One master issue, eight MUST umbrella issue bodies, and exactly twenty-three MUST child issue bodies under `docs/backlog/`.
6. An optional parking lot, labels manifest, Project design, traceability matrix, and ordered GitHub execution plan.
7. Machine-readable JSON manifests for later Gate D execution; they are data only and must not be executed in Gate A.
8. Executed local validation evidence, separated into passed, failed, unavailable, and not-applicable results.

## Repository structure

The selected structure contains root governance and developer files; `configs/`; the `src/intentguard/` package; `scripts/`; unit, contract, integration, and fixture test areas; generated data/artifact/report roots with tracked README files; `docs/specification/` unchanged; concise operational/status/limitations documents; `docs/backlog/`; and GitHub collaboration templates and CPU CI.

No complete specification is copied outside `docs/specification/`.

## Command contract

| Command | Gate A behavior | Owner after implementation |
|---|---|---|
| `make help` | Operational; documents every target | `Makefile` |
| `make setup` | Operational; installs the locked environment | `uv` / `pyproject.toml` / `uv.lock` |
| `make data` | Fails non-zero: tracked by U02 | `scripts/prepare_data.py` |
| `make baseline` | Fails non-zero: tracked by U03 | `scripts/train_baseline.py` |
| `make train` | Fails non-zero: tracked by U04 | `scripts/train_transformer.py` |
| `make evaluate` | Fails non-zero: tracked by U05 | `scripts/evaluate.py` |
| `make serve` | Fails non-zero: tracked by U06 | `src/intentguard/api.py` |
| `make demo` | Fails non-zero: tracked by U06 | `scripts/demo.py` |
| `make lint` | Operational; Ruff plus mypy | project configuration |
| `make test` | Operational; foundation tests only | pytest |

An unimplemented target must never exit successfully.

## Backlog hierarchy

- Master: `[MVP] Deliver IntentGuard Weekend MVP`
- U01: Project foundation and reproducibility (T-001)
- U02: BANKING77 data contract (T-002)
- U03: TF-IDF logistic-regression baseline (T-003)
- U04: DistilBERT training and immutable artifact (T-004)
- U05: Comparative evaluation and selective prediction (T-005)
- U06: FastAPI inference and real-artifact demo (T-006)
- U07: Full validation and acceptance gate (T-007)
- U08: Documentation and recruiter-ready delivery (T-008)

Child issue counts are fixed at 3, 3, 3, 3, 3, 3, 2, and 3 respectively, totaling 23. SHOULD, STRETCH, and POST-WEEKEND work remains only in `docs/backlog/PARKING_LOT.md` during Gate A.

## Primary requirement ownership

Every T-001–T-008, FR-001–FR-010, NFR-001–NFR-010, and AC-001–AC-014 identifier has exactly one primary umbrella and child owner in `docs/backlog/TRACEABILITY.md` and `docs/backlog/traceability.json`. Secondary relationships may be recorded in issue prose but do not create duplicate primary ownership.

## Approval boundaries

- Gate A: approved for local repository preparation only.
- Gate B: separately approve Git initialization and a local commit.
- Gate C: separately approve remote repository creation and initial push.
- Gate D: separately approve GitHub Project, labels, and issue creation.

Stop before any action that requires Gate B, C, or D.

## Gate A acceptance

- Required files and directories exist and the authoritative specification remains in place.
- TOML, JSON, Markdown links, backlog counts, issue-title uniqueness, and traceability ownership validate.
- `uv.lock` is generated and validates; the locked environment installs.
- The package imports; `make help`, `make lint`, and `make test` succeed.
- Python sources compile.
- Future ML commands fail non-zero with their umbrella identifier.
- No secrets or unexpected generated artifacts are found.
- No Git repository is initialized and no remote resource is mutated.

## Stop conditions

Stop and report if existing user files would be overwritten unexpectedly, the specification would be duplicated, an unapproved dependency is required, a secret is found, issue counts differ from 1 + 8 + 23, a validation failure cannot be corrected within Gate A, or a remote mutation is required.
