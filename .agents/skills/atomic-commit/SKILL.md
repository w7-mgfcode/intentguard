---
name: atomic-commit
description: Validate, scope, and prepare one small, evidence-backed Git commit without silently staging unrelated work. Use when a user asks to create, automate, review, or improve commit quality, especially in a dirty repository with multiple workstreams or explicit approval gates.
---

# Atomic commit

Use this skill to turn an approved, coherent change into one auditable local
commit. Prefer the bundled `scripts/commit_gate.py` for deterministic checks.
The skill never pushes, creates remotes, runs GitHub mutations, rewrites
history, or commits without explicit approval for the exact subject and file
scope.

## Workflow

1. Inspect before staging:
   - repository root, branch, HEAD, remotes, upstream, and status;
   - staged and unstaged paths separately;
   - user-owned untracked files and generated artifacts;
   - the requested scope and acceptance evidence.
2. Stop if the requested scope is ambiguous, includes unrelated user changes,
   requires deletion/rewrite, or crosses a remote boundary.
3. Run `scripts/commit_gate.py --message "<subject>"` to produce a read-only
   report. Review its proposed file set, diff hygiene, secret scan, and
   conventional subject checks.
4. Run the narrowest relevant tests and static checks. Record actual commands
   and results; never convert unavailable checks into passes.
5. Obtain explicit approval immediately before staging and committing. The
   approval must identify the exact subject and paths.
6. Stage only the reviewed paths with `git add -- <paths>`. Re-run the gate
   against the staged diff and inspect `git diff --cached`.
7. Create exactly one normal commit with the approved subject. Do not amend,
   rebase, reset, sign by changing configuration, bypass hooks, or force any
   operation.
8. Verify the commit parent, subject, changed paths, tree, clean worktree,
   branch, remotes, and upstream. Do not push unless separately approved.

## `$flow-atom` mode

Use `$flow-atom` when the user requests a full end-to-end atomic commit
decision. The agent should inspect the repository, select one coherent scope,
derive or validate the commit subject, run the available project checks, and
produce a decision: `READY_TO_COMMIT`, `BLOCKED`, `READY_TO_PUSH`, or `PUSHED`.

The mode must:

1. refuse ambiguous scopes; an explicit allow-list may coexist with unrelated
   dirty work, which must be reported and preserved rather than staged;
2. preserve unrelated user changes and untracked files;
3. run the narrowest relevant checks before staging;
4. stage only an explicit reviewed path allow-list;
5. revalidate the staged diff;
6. create one normal commit only with `--approve-commit`;
7. read back the commit and working tree;
8. push only with a separate `--approve-push` and only after verifying the
   expected branch, remote, and commit identity;
9. read back the remote SHA after push and report `PUSHED` only on an exact match;
10. stop immediately on any mismatch, hook failure, secret finding, or scope
    expansion.

`--approve-push` never implies approval to create a remote, alter metadata,
force-push, or modify GitHub resources. The mode never uses `--force`,
`--no-verify`, amend, reset, rebase, or destructive recovery.

## Commit quality rules

- Keep one logical purpose per commit; split unrelated hierarchy, application,
  formatting, and generated changes.
- Use a short imperative Conventional Commit subject: `type: description`.
- Do not stage `.env`, credentials, private keys, model weights, datasets,
  generated reports, caches, or execution-state files.
- Preserve user-owned untracked files; never use `git add .` as a shortcut.
- Treat `docs/specification/` and other authoritative sources as protected
  unless the request explicitly authorizes them.
- For requirement-driven work, report affected T/FR/NFR/AC identifiers and
  executed evidence in the commit handoff or pull request.
- A clean validation report does not itself authorize a commit or push.

## Safe command patterns

Read-only preparation:

```bash
uv run --locked python .agents/skills/atomic-commit/scripts/commit_gate.py \
  --message "docs: update approved hierarchy contract"
```

Full decision flow, still stopping before mutation:

```bash
uv run --locked python .agents/skills/atomic-commit/scripts/commit_gate.py \
  --flow-atom \
  --message "docs: update approved hierarchy contract" \
  --path docs/backlog/github-manifest.json
```

Only after the user approves that exact path, subject, commit, and push may
the executor add `--approve-commit --approve-push`.

After explicit approval, use an explicit path list, then revalidate:

```bash
git add -- docs/backlog/github-manifest.json docs/backlog/GITHUB_EXECUTION_PLAN.md
uv run --locked python .agents/skills/atomic-commit/scripts/commit_gate.py \
  --message "docs: update approved hierarchy contract" --staged-only
git diff --cached --check
git commit -m "docs: update approved hierarchy contract"
```

The skill stops before `git commit` unless the user has approved that exact
operation. It never invokes `git push`.

## Failure handling

- Unexpected paths: stop and list them; do not unstage or delete automatically.
- Secret or credential match: stop and ask for review.
- Validation failure: report the command and failure; do not commit.
- Hook or signing failure: preserve the staged state and report it; do not use
  `--no-verify` or alter signing configuration.
- Remote or upstream mismatch: stop; remote publication is a separate gate.

## Resource

Use [scripts/commit_gate.py](scripts/commit_gate.py) for deterministic,
read-only scope and hygiene checks before and after staging.
