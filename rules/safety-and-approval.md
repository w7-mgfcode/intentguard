# Safety and approval

**Purpose:** Separate inspection, local changes, and external mutations.

**Intended reader:** Agents, developers, and reviewers.

**Consult this when:** A task may change files, Git history, GitHub, CI,
credentials, data, or another external system.

## Mutation classes

| Class | Examples | Default |
|---|---|---|
| Read-only local | Read files, search, `git status`, `git diff`, `git log` | Allowed |
| Read-only remote | `gh repo view`, issue/PR/workflow lists and views | Allowed when relevant and authenticated |
| Local workspace | Edit code, tests, docs; run normal local checks | Allowed only when the user requests implementation |
| Local stateful | Commit, switch branch with risk, modify local database, install dependencies | Ask when not clearly included in the request |
| Remote write | Push, create/edit/close issue, create/edit/merge PR, Project write, workflow dispatch, release, message | Exact current approval required |
| Destructive | Delete data/resources, force-push, rewrite shared history, broad cleanup | Prohibited by default; require explicit scope and safeguards |

## What counts as approval

Approval is valid when the user's current request names or unambiguously
includes the action and target. Examples:

- “Push this branch to `origin`.”
- “Create a draft PR in `owner/repo` from the current branch.”
- “Close issue #42 after the tests pass.”

A general request to inspect, plan, implement locally, validate, or prepare a
PR description is not approval to perform the remote action.

If the target, repository, branch, issue, recipients, or consequences are
ambiguous, resolve them before acting. Approval for one action does not
automatically cover later actions.

## Read-only GitHub examples

```sh
gh auth status
gh repo view --json nameWithOwner,visibility,defaultBranchRef,pushedAt
gh issue list --state all --limit 50
gh issue view 42
gh pr list --state all --limit 30
gh pr view 42
gh pr diff 42
gh pr checks 42
gh project list --owner OWNER --format json
gh workflow list
gh run list --limit 20
```

Command names alone do not prove safety. Review flags and behavior. For
example, `gh pr create --dry-run` may still push Git changes, so FPAT Lite
classifies it as approval-sensitive.

## Remote-write examples

```text
git push
gh issue create|edit|close|reopen|comment
gh pr create|edit|merge|close|ready|review|comment
gh project create|edit|delete|item-add|item-edit|item-delete
gh workflow run
gh release create|edit|delete|upload
```

This list is illustrative, not an allowlist. New or unknown commands must be
classified by effect.

## Secrets and credentials

- Never print tokens, private keys, session cookies, or secret values.
- Do not read `.env`, credential stores, or broad home directories unless the
  task requires it and permission allows it.
- Prefer existing authenticated tools over extracting credentials.
- A configured credential does not grant authority beyond the user's request.

## Destructive-action gate

Before an explicitly requested destructive action:

1. Resolve the exact target with a read-only check.
2. Explain impact and recovery.
3. Prefer a reversible alternative.
4. Avoid unresolved variables, broad globs, or root/home targets.
5. Obtain confirmation when consequences remain material.
6. Report exactly what changed and whether recovery is possible.

## Platform enforcement

These Markdown rules influence agent behavior but do not enforce security.
Use Codex sandbox and approval settings, Claude Code permissions or hooks,
repository branch protection, and CI for hard controls. Do not add a
checked-in permission grant that silently broadens access.

