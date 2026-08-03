# Labels manifest

The manifest owns exactly 16 managed labels: three hierarchy types, four
priority labels, eight area labels, and `status:blocked`. Project fields own
workflow state, priority selection, estimate, and hierarchy. GitHub's default
labels remain unmanaged and are not part of this count.

| Name | Color | Description | Intended usage |
|---|---|---|---|
| `type:umbrella` | `5319E7` | Parent issue coordinating canonical epics | W01–W03 only |
| `type:epic` | `6F42C1` | Substantial MUST deliverable under an umbrella | E01–E08 only |
| `type:subtask` | `1D76DB` | Atomic MUST implementation task under an epic | S01.1–S08.3 only |
| `priority:MUST` | `B60205` | Required for strict Weekend MVP | W/E/S managed issues |
| `priority:SHOULD` | `FBCA04` | Valuable after strict MVP if time permits | Optional work promoted from parking lot |
| `priority:STRETCH` | `0E8A16` | Weekend stretch only | Optional work promoted from parking lot |
| `priority:POST-WEEKEND` | `6E7781` | Explicitly outside Weekend MVP | Deferred work, including Docker |
| `area:foundation` | `C5DEF5` | Packaging, commands, configuration, and repository rules | E01 and W01 foundation scope |
| `area:data` | `0052CC` | Dataset loading, validation, splits, and provenance | E02 and W01 data scope |
| `area:baseline` | `0E8A16` | TF-IDF logistic-regression baseline | U03 work |
| `area:model` | `5319E7` | Transformer training and immutable artifacts | U04 work |
| `area:evaluation` | `D4C5F9` | Metrics, calibration, selective prediction, and reports | U05 work |
| `area:api` | `1D76DB` | Typed FastAPI inference and demo | U06 work |
| `area:quality` | `BFDADC` | Test, CI, acceptance, and quality gates | U07 work |
| `area:documentation` | `0075CA` | README, operations, limitations, and delivery evidence | U08 work |
| `status:blocked` | `D93F0B` | Cannot proceed under current prerequisites or constraints | Add only with a recorded blocker and stop condition |
