# Labels manifest

Labels categorize work; Project fields own workflow state, priority selection, estimate, and hierarchy. Only `status:blocked` duplicates a workflow concern because blocked work must remain conspicuous outside a Project view.

| Name | Color | Description | Intended usage |
|---|---|---|---|
| `type:umbrella` | `5319E7` | Parent issue coordinating one MUST task | U01–U08 only |
| `type:task` | `1D76DB` | Implementable child or defect | C01.1–C08.3 and later bugs |
| `priority:MUST` | `B60205` | Required for strict Weekend MVP | Master, umbrellas, and MUST children |
| `priority:SHOULD` | `FBCA04` | Valuable after strict MVP if time permits | Optional work promoted from parking lot |
| `priority:STRETCH` | `0E8A16` | Weekend stretch only | Optional work promoted from parking lot |
| `priority:POST-WEEKEND` | `6E7781` | Explicitly outside Weekend MVP | Deferred work, including Docker |
| `area:foundation` | `C5DEF5` | Packaging, commands, configuration, and repository rules | U01 work |
| `area:data` | `0052CC` | Dataset loading, validation, splits, and provenance | U02 work |
| `area:baseline` | `0E8A16` | TF-IDF logistic-regression baseline | U03 work |
| `area:model` | `5319E7` | Transformer training and immutable artifacts | U04 work |
| `area:evaluation` | `D4C5F9` | Metrics, calibration, selective prediction, and reports | U05 work |
| `area:api` | `1D76DB` | Typed FastAPI inference and demo | U06 work |
| `area:quality` | `BFDADC` | Test, CI, acceptance, and quality gates | U07 work |
| `area:documentation` | `0075CA` | README, operations, limitations, and delivery evidence | U08 work |
| `status:blocked` | `D93F0B` | Cannot proceed under current prerequisites or constraints | Add only with a recorded blocker and stop condition |
