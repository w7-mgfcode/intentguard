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
- Purpose: inspect all 34 created W/E/S issues without mixing in parking-lot prose.

A tertiary `Title ascending` sort was originally specified here and is
`Blocked` by the platform. GitHub Projects accepts at most two sort criteria per
view. This was confirmed in the UI and independently against the GraphQL API:
the `sort:title-asc` filter term does not register as a third sort, and no
input type in the schema exposes a sort or grouping input at all
(`ProjectV2ViewConfigurationInput` contains only `visibleFieldIds`). Two sort
criteria are therefore the complete, verifiable requirement for this view.

### Umbrella Progress

- Layout: table.
- Filter semantics: `label:type:umbrella`. A quoted or UI-normalized form is
  acceptable only when it selects that exact label.
- Required columns: Status, Priority, Estimate, Sub-issues progress.
- Sort: Title ascending.
- Filter result: exactly the three `type:umbrella` issues `W01`, `W02`, and `W03`.
- Purpose: compact progress over W01–W03; E/S records are inspected in Full Backlog.

## Configuration and verification method

These three views are configured after the automated Gate D workflow has
created and verified the Project, issues, hierarchy, items, fields, and field
values.

Sort order must be configured by the user in the GitHub UI. No GraphQL input
type expresses a sort, so sorting can be read back but never written by an
automated step.

The remaining properties are API-writable and were configured that way:
`createProjectV2View` and `updateProjectV2View` set name, layout, filter, and
visible columns, and setting `BOARD_LAYOUT` makes GitHub populate
`verticalGroupByFields` with Status on its own. An earlier revision of this
document stated that automated view mutation was prohibited because the
available interfaces could not express any required grouping or sorting
property. That was correct for sorting and incorrect for grouping, layout,
filter, and columns.

Any automated view creation must preserve the recorded default view's node ID
by renaming it rather than replacing it, because the runbook rejects a changed
default-view identity.

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

Project configuration is a Gate D remote write. Gate D view completion is
`Implemented`. The three views exist on the remote Project with the layouts,
filters, columns, grouping, and sort orders recorded above; the user configured
every sort order in the GitHub UI and performed the authenticated read-only UI
inspection; the exact attestation is recorded; and all three execution-state
records are complete and `verified`. The final read-only verification and
execution-state finalization both passed, so Gate D is closed.

The only requirement in this document that is not satisfied is the tertiary
`Title ascending` sort on Full Backlog, which remains `Blocked` by the two-sort
platform cap described above.
