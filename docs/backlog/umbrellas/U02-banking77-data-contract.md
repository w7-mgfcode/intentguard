# U02 — BANKING77 data contract

## Objective

Load one pinned `PolyAI/banking77` revision, preserve canonical train/test splits, derive a validation split from training data reproducibly, validate 77 labels, and record provenance.

## Rationale

Stable data identity and split integrity are prerequisites for comparable baseline, transformer, calibration, and test claims.

## Parent identifier

Master issue `[MVP] Deliver IntentGuard Weekend MVP`.

## Source task

T-002.

## Traceability

Primary: T-002, FR-001, AC-001.

## Prerequisites

U01 complete; immutable dataset revision verified; network access or a verified compatible cache.

## Likely files

`configs/default.toml`, `src/intentguard/data.py`, `scripts/prepare_data.py`, `tests/contract/test_data_contract.py`, `tests/unit/test_data.py`, `data/` provenance outputs.

## Implementation boundary

BANKING77 only; no augmentation, external OOD corpus, relabeling, or synthetic replacement in strict mode.

## MUST scope

C02.1 loader and revision pin; C02.2 canonical splits, validation split, labels, and provenance; C02.3 command integration and contract tests.

## Explicit non-goals

Model training, tokenizer fitting, extra datasets, text normalization beyond the declared contract, or unsupported benchmark claims.

## Acceptance criteria

`make data` validates source revision, schema, exact label cardinality, unique label mapping, canonical test isolation, deterministic validation membership, counts, and written provenance.

## Validation commands

`make data && uv run pytest tests/contract/test_data_contract.py tests/unit/test_data.py -q`.

## Expected evidence

Dataset/revision identifiers, split counts and fingerprints, label map, seed, validation construction metadata, license reference, and passing contract tests.

## Fallback and status consequence

A verified cache preserves implementation. A synthetic dataset is Mocked/Partial, removes BANKING77 and benchmark claims, and fails strict MVP.

## Stop condition

Stop for unresolved revision, changed upstream schema, non-77 taxonomy, split overlap, test-label leakage, or unverified cache provenance.

## Definition of ready

U01 passes; revision-selection method is agreed; storage path and provenance schema are reviewed.

## Definition of done

C02.1–C02.3 pass and all data claims are Measured from the pinned dataset contract.

## Labels

`type:umbrella`, `priority:MUST`, `area:data`

## Estimate

2.0 hours.
