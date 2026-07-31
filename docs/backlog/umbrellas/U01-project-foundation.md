# U01 — Project foundation and reproducibility

## Objective

Establish repository governance, Python 3.11 packaging, locked dependencies, reviewed configuration, command contracts, foundation tests, and CPU CI.

## Rationale

Every later result depends on a repeatable environment and an honest command surface; this removes setup ambiguity before ML work begins.

## Parent identifier

Master issue `[MVP] Deliver IntentGuard Weekend MVP`.

## Source task

T-001.

## Traceability

Primary: T-001, FR-010, NFR-003, NFR-007, NFR-008. No numbered AC has primary ownership here; U01 establishes their execution substrate.

## Prerequisites

Approved Gate A plan, MIT confirmation, Python 3.11, and `uv`.

## Likely files

`AGENTS.md`, `CLAUDE.md`, `README.md`, `LICENSE`, `pyproject.toml`, `uv.lock`, `Makefile`, `.gitignore`, `.env.example`, `configs/default.toml`, `src/intentguard/__init__.py`, `src/intentguard/config.py`, `scripts/validate_foundation.py`, skeleton tests, `.github/`.

## Implementation boundary

Foundation only. Do not implement data, model, evaluation, API, or demo behavior and do not let future targets exit successfully.

## MUST scope

C01.1 governance/skeleton; C01.2 packaging/lock/config; C01.3 Make/CI/collaboration and validation scaffolding.

## Explicit non-goals

ML application behavior, downloaded data, trained artifacts, Docker, deployment, extra tooling, or GPU claims.

## Acceptance criteria

The package imports; configuration parses; the lock validates and installs; required files/targets exist; unimplemented commands fail; Ruff, mypy, foundation validation, pytest, and CPU CI are truthfully configured.

## Validation commands

`uv lock --check && make setup && make help && make lint && make test`.

## Expected evidence

`uv.lock`, clean command outputs, foundation-test results, parsed manifests, and a CPU workflow referencing only existing checks.

## Fallback and status consequence

An unlocked or partial environment makes U01 Partial and blocks strict MVP. CPU-only validation is Implemented for this umbrella; it creates no GPU compatibility claim.

## Stop condition

Stop for unapproved dependencies, overwritten user files, secrets, unavailable Python 3.11, lock/install failure, or any required Git/GitHub mutation.

## Definition of ready

Dependencies and boundaries are justified by the specification; Gate A is approved; no conflicting existing foundation exists.

## Definition of done

C01.1–C01.3 pass their validations and the repository reports the actual foundation status without claiming ML completion.

## Labels

`type:umbrella`, `priority:MUST`, `area:foundation`

## Estimate

1.0 hour.
