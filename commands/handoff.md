# Handoff

## Name

`handoff`

## Purpose

Compress current work into one resumable checkpoint for another agent or a
future session.

## When to use

Use when pausing incomplete work, approaching a context limit, switching
agents, waiting for approval, or finishing a stage whose next step is separate.

## Required inputs

- Current objective.
- Repository and worktree state.
- Completed work and validation evidence.

## Optional inputs

- Stage name.
- Issue or pull-request references.
- Pending decision or approval.
- Prior handoff to replace.

## Files to read

- Active plan and request.
- Current diff and Git status.
- Validation output.
- Existing `.fpat/handoff.md`.
- `templates/handoff.md`.

## Allowed tools

- Read-only repository and Git inspection.
- Read-only GitHub inspection when relevant.
- Local write of the checkpoint file.

## Read-only operations

Reconfirm completed files, exact validation commands and results, current
branch, known issues, and remote state. Do not rely only on conversation memory.

## Mutation boundary

Invoking this command authorizes creating or replacing the local
`.fpat/handoff.md` checkpoint. It does not authorize applying pending code
changes, committing, pushing, editing GitHub, or any other remote mutation.

## Step-by-step procedure

1. Determine state: `PLANNING`, `APPLYING`, `BLOCKED`, or `READY`.
2. Restate the objective and current scope.
3. Verify completed work against the worktree and evidence.
4. List files changed without claiming ownership of pre-existing edits.
5. Record decisions and their reasons.
6. Record commands actually run and their results.
7. Record known issues, unresolved questions, and pending approvals.
8. Write one exact next action.
9. Add resume instructions that begin with `prime`.
10. Save the checkpoint atomically when the environment supports it, then
    report its path.

## Expected output

```text
State
Objective
Completed
Files changed
Decisions
Validation evidence
Known issues
Pending approvals
Next action
Resume instructions
```

## Validation checklist

- [ ] The checkpoint matches current Git state.
- [ ] Evidence includes commands and real outcomes.
- [ ] Pending mutations were not applied.
- [ ] The next action is singular and executable.
- [ ] Another session can resume without hidden conversation context.

## Stop conditions

Stop before writing if the repository cannot be identified, current state
cannot be verified, or replacing an existing handoff would discard material
information.

## Failure handling

Return the complete checkpoint in the response, explain why local saving failed,
and identify the exact path the user can create manually.

## Example invocation

```text
/fpat-lite handoff waiting for approval to open a pull request
```

## Example response

```text
Saved .fpat/handoff.md with state READY. Local implementation and validation are
complete. Pending approval: push the branch and create a draft pull request.
Next session: run prime, verify the recorded Git state, then request the specific
remote action again if approval is still current.
```

