# Requirement-to-Test Traceability

## Functional traceability

| Requirement | Acceptance criteria | Planned validation |
|---|---|---|
| FR-001 Dataset preparation | AC-001 | `test_data_contract.py`, `make data` |
| FR-002 Baseline | AC-002, AC-004 | `test_baseline.py`, `make baseline`, `make evaluate` |
| FR-003 Transformer | AC-003, AC-004 | `test_training_smoke.py`, `make train`, `make evaluate` |
| FR-004 Abstention | AC-005–AC-007 | `test_threshold.py`, API integration tests |
| FR-005 Evaluation | AC-004, AC-011, AC-012 | `test_metrics.py`, `test_eval_regression.py` |
| FR-006 Inference API | AC-006–AC-008 | `test_api.py` |
| FR-007 Health check | AC-009 | `test_health.py` |
| FR-008 Artifact persistence | AC-003, AC-009, AC-010 | `test_artifacts.py`, save/load parity |
| FR-009 Unsupported fixture | AC-012 | `test_unsupported_report.py`, `make evaluate` |
| FR-010 Commands | AC-013, AC-014 | CI plus clean-environment manual validation |

## Non-functional traceability

| Requirement | Acceptance criteria/evidence | Planned validation |
|---|---|---|
| NFR-001 Local compatibility | Engineering success, final validation | Resource observation in `environment.json` |
| NFR-002 CPU support | AC-009, AC-013 | CPU CI and forced-CPU API smoke |
| NFR-003 Reproducibility | AC-001–AC-005, AC-010–AC-011 | metadata assertions, lockfile, repeated fixture run |
| NFR-004 Input safety | AC-008 | API boundary tests |
| NFR-005 Logging privacy | AC-014 | captured-log test |
| NFR-006 Performance reporting | AC-004 | `latency.json` schema and evaluation command |
| NFR-007 Maintainability | AC-014 | Ruff, mypy, review of module boundaries |
| NFR-008 Dependency control | AC-014 | lockfile installation in CI |
| NFR-009 Testability | AC-010–AC-014 | unit/contract/integration suite |
| NFR-010 Honest reporting | AC-004, AC-012, AC-014 | report/README validation checklist |

## User-story traceability

| User story | Requirements |
|---|---|
| US-001 Validated data | FR-001, FR-010, NFR-003 |
| US-002 Baseline comparison | FR-002, FR-003, FR-005 |
| US-003 Safe abstention | FR-004, FR-006, FR-009 |
| US-004 Typed local inference | FR-006–FR-008 |
| US-005 Verifiable claims | FR-005, FR-010, NFR-010 |

## Traceability maintenance rule

When behavior changes:

1. update the requirement or add an approved requirement;
2. update acceptance criteria;
3. update the nearest test;
4. update this matrix;
5. update the relevant ADR if a decision changed.

Agents must not add orphan behavior that has no requirement and no validation.

