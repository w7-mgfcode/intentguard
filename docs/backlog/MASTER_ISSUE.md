# [MVP] Deliver IntentGuard Weekend MVP

## Objective

Deliver one coherent, reproducible IntentGuard system that validates BANKING77, measures a lexical baseline and a fine-tuned DistilBERT classifier, applies validation-selected selective prediction, and serves the immutable transformer artifact through a typed FastAPI boundary.

## Rationale

The project demonstrates end-to-end ML engineering judgment—comparison, calibration, abstention, reproducibility, typed inference, and honest evidence—within a fixed weekend boundary.

## Parent identifier

None. This is the top-level parent for U01–U08.

## Source task

T-001 through T-008.

## Traceability

Program parent for FR-001–FR-010, NFR-001–NFR-010, and AC-001–AC-014. Primary ownership remains singular in `TRACEABILITY.md`.

## Prerequisites

Approved authoritative specification, fixed brainstorm decisions, Python 3.11, `uv`, adequate local CPU/RAM, and compatible GPU access only when U04 training is attempted.

## Likely files

`AGENTS.md`, `README.md`, `pyproject.toml`, `uv.lock`, `Makefile`, `configs/`, `src/intentguard/`, `scripts/`, `tests/`, `data/`, `artifacts/`, `reports/`, `docs/`, and `.github/`.

## Implementation boundary

Coordinate the eight umbrellas without adding a second dataset, model family, public interface, or specification source. Freeze scope after U01/U02 readiness and require a working baseline checkpoint before transformer work becomes the critical path.

## MUST scope

U01 foundation; U02 pinned BANKING77 contract; U03 TF-IDF logistic baseline; U04 fine-tuned DistilBERT plus immutable validation threshold; U05 comparable and selective evaluation; U06 typed FastAPI plus real-artifact demo; U07 full validation; U08 honest recruiter-ready documentation.

## Explicit non-goals

All SHOULD, STRETCH, and POST-WEEKEND items; Docker; deployment; alternate datasets or models; frontend; database; experiment platform; production monitoring; invented performance targets.

## Acceptance criteria

All U01–U08 definitions of done are satisfied; AC-001–AC-014 pass; every MUST is Implemented; applicable dataset/model/evaluation claims are Measured; the scope-freeze and working-baseline checkpoints are recorded; no fallback is misrepresented.

## Validation commands

`make setup && make data && make baseline && make train && make evaluate && make lint && make test`, followed by `make serve` and `make demo` in separate terminals as documented.

## Expected evidence

Pinned provenance, immutable artifacts, machine-readable reports, CPU CI, passing tests and static checks, typed API examples, real-artifact demo output, status audit, limitations, and a reviewed Sunday completion checklist.

## Fallback and status consequence

Synthetic data removes BANKING77 benchmark claims; frozen embeddings make FR-003 Partial; deterministic prediction is Mocked outside real serving; one-epoch training is only Implemented if the fine-tuned MUST behavior genuinely exists and is Measured; CPU-only execution is valid except for unmade GPU claims. Any violated MUST fails strict MVP.

## Stop condition

Stop the strict-MVP claim for missing MUST behavior, test-label leakage, irreproducible provenance, invalid artifact/API contracts, absent real-artifact demo, or unmeasured required claims. Move optional work out before extending the weekend.

## Definition of ready

The eight umbrellas have approved boundaries, singular traceability owners, estimates, prerequisites, and implementation-ready child issues; scope is frozen.

## Definition of done

Every child is done, all acceptance evidence is executed and reviewed, statuses are honest, documentation matches outputs, and no optional or degraded path is presented as strict completion.

## Labels

`type:umbrella`, `priority:MUST`

## Estimate

16 hours total child effort, excluding model download/training wall time.
