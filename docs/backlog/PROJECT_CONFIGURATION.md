# Project configuration

## Identity

- Title: `IntentGuard — Weekend MVP`
- Visibility: public
- Repository: `w7-mgfcode/intentguard`
- Repository visibility: public
- Description: `Confidence-aware support intent classification with reproducible evaluation, selective prediction and a typed FastAPI inference boundary.`

## Fields

| Field | Type and values | Purpose |
|---|---|---|
| Status | Built-in single select: Backlog, Ready, In progress, Review, Done | Only workflow-state source |
| Priority | Single select: MUST, SHOULD, STRETCH, POST-WEEKEND | Scope boundary and ordering |
| Estimate | Number, hours | Coarse weekend capacity check; child values roll up conceptually |
| Parent issue | Built-in hierarchy | Master-to-umbrella and umbrella-to-child context |
| Sub-issue progress | Built-in progress | Evidence-based roll-up without manual percentage fields |

No dates, owners, risk scores, iterations, or automation are added initially.

## Views

### MVP Board

- Layout: board.
- Filter: `Priority:MUST`.
- Group: Status.
- Sort: Priority, then Estimate ascending.
- Purpose: the smallest actionable strict-MVP view.

### Full Backlog

- Layout: table.
- Filter: all real issues.
- Columns: Status, Priority, Parent issue, Estimate, Labels.
- Sort: Priority, then Parent issue, then title.
- Purpose: inspect all created work without mixing in parking-lot prose.

### Umbrella Progress

- Layout: table.
- Filter: `label:type:umbrella`.
- Columns: Status, Priority, Estimate, Sub-issue progress.
- Sort: title ascending.
- Purpose: compact progress over U01–U08.

Project configuration is a Gate D remote write and remains unexecuted.
