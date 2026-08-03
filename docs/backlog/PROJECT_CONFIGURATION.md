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
| Status | Built-in single select: exactly Backlog, Ready, In progress, Review, Done | Only workflow-state source |
| Priority | Single select: MUST, SHOULD, STRETCH, POST-WEEKEND | Scope boundary and ordering |
| Estimate | Number, hours | Subtask values are primary; epic and umbrella progress is interpreted as native sub-issue roll-up |
| Parent issue | Built-in hierarchy | Umbrella-to-epic and epic-to-subtask context; M1 is the native milestone |
| Sub-issues progress | Built-in progress | Evidence-based roll-up without manual percentage fields |

No dates, owners, risk scores, iterations, or automation are added initially.

The Status option list is exact, not a minimum. A new ProjectV2 ships built-in
`Todo`, `In Progress`, and `Done` options; the two that the table above does not
name were removed so the live field matches this contract. Removing an option
clears that value from every item holding it, so an extra option is removed only
after a complete, paginated scan proves no item uses it, and an extra option in
use stops for a decision instead. The five retained options keep their original
option IDs, which is asserted on read-back because resubmitting a name without
its ID would delete and recreate the option and silently clear item values.

## Views

### MVP Board

- Layout: board.
- Filter: `Priority:MUST`.
- Group: Status.
- Primary sort: Priority in the configured field-option order, which is
  ascending (`MUST`, `SHOULD`, `STRETCH`, `POST-WEEKEND`).
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

Two corrections were made after Gate D finalization. The user set the MVP Board
primary sort to the ascending field-option order; the recorded view expectation
stores that criterion as the direction string `field-option-order`, which does
not distinguish ascending from descending, so the automated checks could not
have caught the earlier descending setting. The two non-manifest Status options
were then removed. Neither correction altered any recorded execution-state
value: the state stores the Status field ID and the `Backlog` option ID, both of
which are unchanged, so the finalized state remains accurate and was not
rewritten. Status is `Measured` for the live field contents and `Implemented`
for the reconciliation logic.

One property could not be verified. GitHub's GraphQL schema exposes no action or
configuration detail for `ProjectV2Workflow`, so whether the enabled built-in
`Item added to project` workflow referenced the removed `Todo` option could not
be read back. Section 14 already overwrites GitHub's `Todo` default on every
item it populates, and all 34 items read back as `Backlog` after the removal, so
no observed item value depends on it.
