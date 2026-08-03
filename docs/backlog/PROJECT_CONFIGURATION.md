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
| Estimate | Number, hours | Subtask values are primary; epic and umbrella progress is interpreted as native sub-issue roll-up |
| Parent issue | Built-in hierarchy | Umbrella-to-epic and epic-to-subtask context; M1 is the native milestone |
| Sub-issues progress | Built-in progress | Evidence-based roll-up without manual percentage fields |

No dates, owners, risk scores, iterations, or automation are added initially.

## Views

### MVP Board

- Layout: board.
- Filter: `Priority:MUST`.
- Group: Status.
- Primary sort: Priority in the configured field-option order.
- Secondary sort: Estimate ascending.
- Scope: all 34 managed M1 issues (W/E/S), filtered to `Priority:MUST`.
- Purpose: the smallest actionable strict-MVP view.

### Full Backlog

- Layout: table.
- Filter: all real issues, represented in the GitHub UI by no active filter.
- Required columns: Status, Priority, Parent issue, Estimate, Labels.
- Primary sort: Priority in the configured field-option order.
- Secondary sort: Parent issue ascending.
- Tertiary sort: Title ascending.
- Purpose: inspect all 34 created W/E/S issues without mixing in parking-lot prose.

### Umbrella Progress

- Layout: table.
- Filter semantics: `label:type:umbrella`. A quoted or UI-normalized form is
  acceptable only when it selects that exact label.
- Required columns: Status, Priority, Estimate, Sub-issues progress.
- Sort: Title ascending.
- Filter result: exactly the three `type:umbrella` issues `W01`, `W02`, and `W03`.
- Purpose: compact progress over W01–W03; E/S records are inspected in Full Backlog.

## Configuration and verification method

The user manually configures these three views after the automated Gate D
workflow has created and verified the Project, issues, hierarchy, items,
fields, and field values. Automated view mutation is prohibited for this
approved configuration because the available GitHub CLI/API interfaces cannot
express and read back every required grouping and multi-field sorting
property.

Gate D view completion requires all of the following:

- exactly the three named views above, with no extra managed or unexpected
  view;
- authenticated, read-only GitHub UI inspection of each view's Project
  identity, name, layout, filter, visible fields or columns, grouping, and full
  sorting order;
- the user's exact configuration attestation recorded by the execution
  runbook;
- one complete, verified execution-state record per view.

Screenshots may supplement the authenticated UI inspection, but cannot replace
it and cannot independently authorize `verified=true`. A pending, blocked,
manual-required, incomplete, duplicated, or mismatched view is not completed
and prevents Gate D finalization.

Project configuration is a Gate D remote write and remains unexecuted.
