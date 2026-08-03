# Ordered GitHub execution plan

This is an inert, command-complete runbook for approved Gates C and D. The
commands in this document are examples for a future approved execution; they
must not be run while preparing or validating this documentation. Gate C
authorizes repository creation, remote configuration, and the reviewed push.
Gate D separately authorizes labels, the Project, fields, issues, hierarchy,
items, field values, and views. Resource adoption is never implicit: an exact
remote match that is absent from execution state is unowned until a separate,
identity-specific approval and adoption operation succeeds.

Run every block below from the reviewed repository root in the order stated by
the **Ordered gate checklist**. Gate D intentionally runs section 8 before
section 7 so Project creation and its possible default-view side effect are
captured first. Use one Bash session through the automated Gate D boundary,
then start a reviewed resume session for the authenticated UI-evidence import
after the user finishes the manual view configuration. Never print
credentials, silently switch accounts, use `--force`, delete and recreate a
resource as recovery, or use
`gh pr create --dry-run`. Every mutation is additive, immediately read back,
and recorded in the ignored `.fpat/github-execution-state.json`. A matching
remote resource that is not recorded in state requires explicit adoption; it
is never silently claimed by this runbook.

## Safety and operation classes

| Class | Meaning |
|---|---|
| READ-ONLY | Inspect local or remote state without changing it. |
| LOCAL WRITE | Change reviewed local Git/runtime state only. |
| REMOTE WRITE | Change GitHub and require the named Gate C or D approval. |
| DESTRUCTIVE OR HIGH-RISK | Delete, transfer, force-update, replace, or unexpectedly change visibility/ownership. Not authorized. |

For every REMOTE WRITE, the operation heading names its approval gate, the
preceding checks are prerequisites, the returned URL or node ID is captured,
the resource is read back before the operation is marked verified, and any
failure is recorded before execution stops. HTTP 401 or 403, invalid
credentials, an unexpected owner/visibility, a duplicate Project title, or a
conflicting label/resource is an immediate stop condition. Authentication
repair is a separate user action before Gate C or D; this runbook never runs
`gh auth refresh` and never exposes a token.

## 1. Runtime prerequisites and task variables — READ-ONLY

The following is the single initialization block. It assigns every task-level
`IG_*` variable consumed later. Values created remotely start empty and acquire
an executable assignment in their owning section. Do not repurpose `HOME`,
`CODEX_HOME`, or another system variable.

```bash
set -euo pipefail

export IG_MANIFEST_FILE='docs/backlog/github-manifest.json'
export IG_TRACEABILITY_FILE='docs/backlog/traceability.json'
export IG_STATE_FILE='.fpat/github-execution-state.json'
export IG_API_VERSION='2022-11-28'
export IG_CURRENT_OPERATION='01-prerequisites'
export IG_TEMP_DIR="$(mktemp -d /tmp/intentguard-github.XXXXXX)"

mapfile -d '' -t ig_static_values < <(
  uv run --locked python - "$IG_MANIFEST_FILE" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
values = (
    manifest["repository"]["owner"],
    manifest["repository"]["name"],
    manifest["repository"]["visibility"],
    manifest["repository"]["description"],
    manifest["project"]["title"],
)
for value in values:
    if not isinstance(value, str) or not value:
        raise SystemExit("manifest contains an empty static value")
    sys.stdout.buffer.write(value.encode("utf-8") + b"\0")
PY
)
test "${#ig_static_values[@]}" -eq 5

export IG_OWNER="${ig_static_values[0]}"
export IG_REPO_NAME="${ig_static_values[1]}"
export IG_REPO="${IG_OWNER}/${IG_REPO_NAME}"
export IG_REPO_VISIBILITY="${ig_static_values[2]}"
export IG_DESCRIPTION="${ig_static_values[3]}"
export IG_PROJECT_TITLE="${ig_static_values[4]}"

export IG_PROJECT_NUMBER=''
export IG_PROJECT_ID=''
export IG_PROJECT_URL=''
export IG_PRIORITY_FIELD_ID=''
export IG_STATUS_FIELD_ID=''
export IG_ESTIMATE_FIELD_ID=''
export IG_PARENT_FIELD_ID=''
export IG_SUB_ISSUE_PROGRESS_FIELD_ID=''
export IG_MUST_OPTION_ID=''
export IG_BACKLOG_OPTION_ID=''
export IG_MASTER_NUMBER=''
export IG_MASTER_ID=''
export IG_MASTER_URL=''
export IG_OWNER_ID=''
export IG_OWNER_TYPE=''
export IG_REPOSITORY_ID=''
export IG_REMOTE_URL=''
export IG_LOCAL_HEAD=''
export IG_REMOTE_HEAD=''
export IG_MUTATION_STDOUT="${IG_TEMP_DIR}/mutation.stdout"
export IG_MUTATION_STDERR="${IG_TEMP_DIR}/mutation.stderr"
export IG_FIELDS_JSON_FILE="${IG_TEMP_DIR}/fields.json"
export IG_ITEMS_JSON_FILE="${IG_TEMP_DIR}/items.json"
export IG_VIEWS_JSON_FILE="${IG_TEMP_DIR}/views.json"
export IG_UI_EVIDENCE_FILE="${IG_TEMP_DIR}/authenticated-ui-view-evidence.json"
export IG_CLI_SUBISSUE_MODE='graphql'

command -v bash >/dev/null
command -v gh >/dev/null
command -v uv >/dev/null
uv run --locked python -c 'import sys; assert sys.version_info[:2] == (3, 11)'

if command -v sha256sum >/dev/null; then
  ig_sha256() {
    local digest remainder
    read -r digest remainder < <(sha256sum "$1")
    printf '%s\n' "$digest"
  }
else
  ig_sha256() {
    uv run --locked python - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
  }
fi

test -f "$IG_MANIFEST_FILE"
test -f "$IG_TRACEABILITY_FILE"
test "$IG_OWNER" = 'w7-mgfcode'
test "$IG_REPO_NAME" = 'intentguard'
test "$IG_REPO" = 'w7-mgfcode/intentguard'
test "$IG_REPO_VISIBILITY" = 'public'
test -n "$IG_PROJECT_TITLE"
test -d "$(dirname "$IG_STATE_FILE")"
test -d "$IG_TEMP_DIR"
gh --version
```

Before Gate C or D, inspect authentication and scopes without printing a token:

```bash
IG_CURRENT_OPERATION='01-authentication-and-scopes'
if ! gh auth status; then
  printf '%s\n' 'STOP: GitHub credentials are invalid; repair authentication as a separate user action.' >&2
  exit 1
fi
ig_auth_login="$(gh api user --jq .login)"
test -n "$ig_auth_login"
test "$ig_auth_login" = "$IG_OWNER"

ig_owner_json="$(gh api "users/${IG_OWNER}")"
mapfile -d '' -t ig_owner_values < <(
  uv run --locked python - "$ig_owner_json" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
for key in ("type", "id"):
    value = str(data[key])
    if not value:
        raise SystemExit(f"empty owner {key}")
    sys.stdout.buffer.write(value.encode() + b"\0")
PY
)
test "${#ig_owner_values[@]}" -eq 2
IG_OWNER_TYPE="${ig_owner_values[0]}"
IG_OWNER_ID="${ig_owner_values[1]}"
case "$IG_OWNER_TYPE" in User|Organization) ;; *) exit 1 ;; esac

# A successful Project listing proves usable Project read scope. A 401/403 stops.
gh project list --owner "$IG_OWNER" --limit 100 --format json > "${IG_TEMP_DIR}/scope-projects.json"
uv run --locked python -m json.tool "${IG_TEMP_DIR}/scope-projects.json" >/dev/null

# After the repository exists, this must report ADMIN or MAINTAIN before writes.
if gh repo view "$IG_REPO" --json viewerPermission > "${IG_TEMP_DIR}/scope-repository.json" 2>/dev/null; then
  uv run --locked python - "${IG_TEMP_DIR}/scope-repository.json" <<'PY'
import json
import sys
from pathlib import Path
permission = json.loads(Path(sys.argv[1]).read_text())["viewerPermission"]
if permission not in {"ADMIN", "MAINTAIN"}:
    raise SystemExit(f"insufficient repository permission: {permission}")
PY
fi
```

Invalid credentials, an unexpected authenticated account, missing repository
write permission, or a Project API 401/403 stops execution. Credential repair
is not part of Gates C/D execution and must be explicitly performed by the
user. Never run `gh auth token`, print authorization headers, or dump the
environment.

## 2. Validate and stream the machine manifest — READ-ONLY

### Gate D migration preflight — mandatory read-only stop

Before entering any section labelled `REMOTE WRITE, Gate D`, execute the
following preflight in the same shell. It performs no state or GitHub write.
The preflight must run before labels, Project, fields, milestone, issues,
relationships, items, or views are touched. The current pre-migration state is
expected to fail with `STATE_MIGRATION_REQUIRED`.

```bash
ig_gate_d_migration_preflight() {
  uv run --locked python - "$IG_MANIFEST_FILE" "$IG_STATE_FILE" "$IG_REPO" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
state_path = Path(sys.argv[2])
repository_name = sys.argv[3]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
state = json.loads(state_path.read_text(encoding="utf-8"))
current_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
if state.get("schema_version") != 1:
    raise SystemExit("STATE_MIGRATION_REQUIRED: state container schema must remain 1")
if state.get("hierarchy_version") != 2 or state.get("manifest_sha256") != current_sha:
    raise SystemExit("STATE_MIGRATION_REQUIRED: audited hierarchy-v2 state migration is required")
local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
remote_line = subprocess.check_output(
    ["git", "ls-remote", repository_name, "refs/heads/main"], text=True
).strip()
remote_sha = remote_line.split()[0] if remote_line else ""
history = state.get("migration_history")
if not isinstance(history, list) or not any(
    row.get("migration_id") == "hierarchy-v2"
    and row.get("verified") is True
    and row.get("from_manifest_sha256") == manifest["migration"]["migration_from_manifest_sha256"]
    and row.get("to_manifest_sha256") == current_sha
    and row.get("commit_sha") == local_sha == remote_sha
    and row.get("state_reset") is False
    for row in history
    if isinstance(row, dict)
):
    raise SystemExit("STATE_MIGRATION_REQUIRED: verified hierarchy-v2 migration history is missing")
if len(state.get("attempt_history", [])) != 18 or len(state.get("failure_history", [])) != 3:
    raise SystemExit("STATE_MIGRATION_REQUIRED: Gate C history must be preserved")
if state.get("failed_operation") is not None or state.get("error") is not None:
    raise SystemExit("STATE_MIGRATION_REQUIRED: active failure must be cleared")
if state.get("state_reset", False) is not False:
    raise SystemExit("STATE_MIGRATION_REQUIRED: state_reset must remain false")
if any(
    state.get(section)
    for section in ("milestone", "labels", "issues", "hierarchy", "project_items", "fields", "views")
):
    raise SystemExit("STATE_MIGRATION_REQUIRED: Gate D collections must be empty before first run")
if state.get("repository", {}).get("verified") is not True:
    raise SystemExit("STATE_MIGRATION_REQUIRED: Gate C repository evidence is missing")
print("Gate D migration preflight passed")
PY
}

# Mandatory before the first Gate D mutation. The current state intentionally
# stops here until a separately approved, pushed and read-back-verified
# hierarchy-v2 migration is recorded.
ig_gate_d_migration_preflight || exit $?
```

No later Gate D block may bypass this function. It is a hard stop, not a
recoverable partial Gate D operation.

These helpers parse only `github-manifest.json`. Records are deterministic
compact JSON terminated by NUL, so titles and paths containing whitespace are
safe. Issue records are enriched in memory with `resolved_labels` and
`initial_status`; the manifest file is never changed.

```bash
ig_manifest_stream() {
  local stream_name="$1"
  uv run --locked python - "$IG_MANIFEST_FILE" "$stream_name" <<'PY'
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
stream = sys.argv[2]
m = json.loads(path.read_text(encoding="utf-8"))
labels = m["labels"]
issues = sorted(m["issues"], key=lambda row: row["creation_order"])
label_names = {row["name"] for row in labels}

if m.get("schema_version") != 2 or m.get("migration", {}).get("hierarchy_version") != 2:
    raise SystemExit("manifest schema 2 and hierarchy version 2 are required")
if len(labels) != 16 or len(label_names) != 16:
    raise SystemExit("manifest must contain 16 unique managed labels")
counts = Counter(row.get("type") for row in issues)
if counts != {"umbrella": 3, "epic": 8, "subtask": 23} or len(issues) != 34:
    raise SystemExit(f"invalid issue inventory: {dict(counts)}")
ids = [row["id"] for row in issues]
orders = [row["creation_order"] for row in issues]
if len(set(ids)) != 34 or len(set(orders)) != 34 or orders != list(range(1, 35)):
    raise SystemExit("issue IDs or creation_order values are not unique and contiguous")
by_id = {row["id"]: row for row in issues}
if m.get("milestone", {}).get("id") != "M1" or any(row.get("milestone_id") != "M1" or "milestone" in row for row in issues):
    raise SystemExit("manifest must define M1 and assign every issue to it")

priority_field = next(
    (field for field in m["project"]["fields"] if field["name"] == "Priority"), None
)
status_field = next(
    (field for field in m["project"]["fields"] if field["name"] == "Status"), None
)
if not priority_field or not status_field or "Backlog" not in status_field["options"]:
    raise SystemExit("required Priority or Status configuration is missing")

enriched = []
for row in issues:
    if row.get("priority") not in priority_field["options"]:
        raise SystemExit(f"unsupported priority for {row['id']}")
    estimate = row.get("estimate_hours")
    if not isinstance(estimate, (int, float)) or isinstance(estimate, bool) or estimate < 0:
        raise SystemExit(f"invalid numeric estimate for {row['id']}")
    if row["type"] == "subtask":
        if row.get("estimate_kind") != "direct" or row.get("expected_rollup") is not None or row.get("rollup_children") != []:
            raise SystemExit(f"invalid direct estimate contract for {row['id']}")
    else:
        if row.get("estimate_kind") != "derived-rollup" or not isinstance(row.get("expected_rollup"), (int, float)):
            raise SystemExit(f"invalid derived estimate contract for {row['id']}")
        children = row.get("rollup_children")
        if not isinstance(children, list) or len(children) != len(set(children)):
            raise SystemExit(f"invalid rollup children for {row['id']}")
    if not Path(row["body_file"]).is_file():
        raise SystemExit(f"missing body file for {row['id']}")
    resolved_labels = row.get("labels", [])
    if not resolved_labels or any(name not in label_names for name in resolved_labels):
        raise SystemExit(f"unknown resolved label for {row['id']}")
    enriched.append({**row, "resolved_labels": resolved_labels, "initial_status": "Backlog"})
if sum(float(row["estimate_hours"]) for row in enriched if row["type"] == "subtask") != 16.0:
    raise SystemExit("direct subtask estimate total must equal 16 hours")
project_items = {row["id"]: row for row in m["project_items"]}
if len(project_items) != 34:
    raise SystemExit("manifest must contain 34 Project items")
for row in enriched:
    item = project_items.get(row["id"])
    if not item or not isinstance(item.get("estimate_hours"), (int, float)) or isinstance(item.get("estimate_hours"), bool):
        raise SystemExit(f"Project Estimate assignment is missing for {row['id']}")
    if item.get("estimate_kind") != row.get("estimate_kind") or item.get("expected_rollup") != row.get("expected_rollup") or item.get("rollup_children") != row.get("rollup_children"):
        raise SystemExit(f"Project rollup contract mismatch for {row['id']}")

edges = []
for edge_index, group in enumerate(m["relationships"]):
    parent = group["parent"]
    if parent not in by_id:
        raise SystemExit(f"unknown relationship parent: {parent}")
    relationship_type = group.get("relationship_type")
    if relationship_type not in {"umbrella-epic", "epic-subtask"}:
        raise SystemExit("relationship_type is missing or invalid")
    child = group.get("child")
    if child not in by_id or by_id[child]["parent"] != parent:
        raise SystemExit(f"invalid relationship: {parent}->{child}")
    expected_type = "umbrella-epic" if by_id[parent]["type"] == "umbrella" and by_id[child]["type"] == "epic" else "epic-subtask"
    if relationship_type != expected_type:
        raise SystemExit(f"relationship_type does not match parent/child types: {parent}->{child}")
    edges.append({
        "key": f"{parent}->{child}",
        "parent": parent,
        "child": child,
        "relationship_type": relationship_type,
        "creation_order": edge_index,
    })
if len(edges) != 31 or len({edge["child"] for edge in edges}) != 31:
    raise SystemExit("manifest must contain 31 unique child relationships")
if sum(edge["relationship_type"] == "umbrella-epic" for edge in edges) != 8:
    raise SystemExit("manifest must contain 8 umbrella-epic relationships")
if sum(edge["relationship_type"] == "epic-subtask" for edge in edges) != 23:
    raise SystemExit("manifest must contain 23 epic-subtask relationships")

for issue in issues:
    seen = set()
    current = issue
    while current.get("parent") is not None:
        if current["id"] in seen:
            raise SystemExit("hierarchy cycle detected")
        seen.add(current["id"])
        parent = current["parent"]
        if parent not in by_id:
            raise SystemExit(f"unknown parent: {parent}")
        current = by_id[parent]

streams = {
    "labels": labels,
    "milestone": [m["milestone"]],
    "umbrellas": [row for row in enriched if row["type"] == "umbrella"],
    "epics": [row for row in enriched if row["type"] == "epic"],
    "subtasks": [row for row in enriched if row["type"] == "subtask"],
    "relationships": edges,
    "project-items": enriched,
    "priorities": [{"id": row["id"], "priority": row["priority"]} for row in enriched],
    "estimates": [{"id": row["id"], "estimate_hours": row["estimate_hours"]} for row in enriched],
    "statuses": [{"id": row["id"], "status": "Backlog"} for row in enriched],
    "views": m["project"]["views"],
}
if stream == "validate":
    print(json.dumps({
        "milestone": 1, "umbrellas": counts["umbrella"], "epics": counts["epic"],
        "subtasks": counts["subtask"], "issues": len(issues),
        "relationships": len(edges), "labels": len(labels),
    }, sort_keys=True))
    raise SystemExit(0)
if stream not in streams:
    raise SystemExit(f"unknown manifest stream: {stream}")
for record in streams[stream]:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sys.stdout.buffer.write(payload.encode("utf-8") + b"\0")
PY
}

ig_json_fields() {
  local payload="$1"
  shift
  uv run --locked python - "$payload" "$@" <<'PY'
import json
import sys
value = json.loads(sys.argv[1])
for key in sys.argv[2:]:
    part = value[key]
    if isinstance(part, (dict, list)):
        part = json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    elif part is None:
        part = ""
    else:
        part = str(part)
    sys.stdout.buffer.write(part.encode("utf-8") + b"\0")
PY
}

ig_json_array_stream() {
  local payload="$1"
  uv run --locked python - "$payload" <<'PY'
import json
import sys
for value in json.loads(sys.argv[1]):
    sys.stdout.buffer.write(str(value).encode("utf-8") + b"\0")
PY
}

ig_manifest_stream validate
for ig_stream in labels milestone umbrellas epics subtasks relationships project-items priorities estimates statuses views; do
  ig_stream_count=0
  while IFS= read -r -d '' ig_record; do
    ig_stream_count=$((ig_stream_count + 1))
  done < <(ig_manifest_stream "$ig_stream")
  printf '%s=%s\n' "$ig_stream" "$ig_stream_count"
done
```

Expected counts are `16, 1, 3, 8, 23, 31, 34, 34, 34, 34, 3` in the
order printed. Validation stops before mutation on a duplicate identifier or
creation order, invalid parent, cycle, missing body, unknown label/priority,
missing estimate, or any inventory mismatch.

## 3. Atomic execution-state initialization — LOCAL WRITE, Gate C/D

Create the state only after the applicable remote gate has been approved. An
existing state is never overwritten. The temporary file is created beside the
destination so `os.replace` remains atomic.

```bash
IG_CURRENT_OPERATION='03-initialize-execution-state'
test ! -e "$IG_STATE_FILE"
uv run --locked python - "$IG_MANIFEST_FILE" "$IG_STATE_FILE" <<'PY'
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

manifest = Path(sys.argv[1])
state = Path(sys.argv[2])
if state.exists():
    raise SystemExit("refusing to overwrite existing execution state")
document = {
    "schema_version": 1,
    "hierarchy_version": 2,
    "manifest_path": str(manifest),
    "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    "repository": {},
    "milestone": {},
    "project": {},
    "labels": {},
    "issues": {},
    "hierarchy": {},
    "project_items": {},
    "fields": {},
    "views": {},
    "adoption_required": None,
    "adoption_history": [],
    "attempt_history": [],
    "failure_history": [],
    "last_attempted_operation": None,
    "last_verified_operation": None,
    "failed_operation": None,
    "error": None,
    "completed": False,
    "finalized_at": None,
    "state_sha256": "",
}
state.parent.mkdir(parents=False, exist_ok=True)
handle = tempfile.NamedTemporaryFile(
    mode="w", encoding="utf-8", dir=state.parent,
    prefix=".github-execution-state.", suffix=".tmp", delete=False,
)
temporary = Path(handle.name)
try:
    with handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    json.loads(temporary.read_text(encoding="utf-8"))
    os.replace(temporary, state)
finally:
    if temporary.exists():
        temporary.unlink()
json.loads(state.read_text(encoding="utf-8"))
PY
```

`adoption_required` holds at most one active stop condition.
`adoption_history` is append-only. Each adopted-resource record contains the
resource type, manifest identifier, remote identifier, expected and observed
properties, the exact approval reference and timestamp, `source=adopted`, a
verified flag, and a verification timestamp. Created resources use
`source=created`; they do not fabricate approval evidence. Authentication
details, tokens, headers, and environment dumps are never state fields.

### Hierarchy migration contract

The manifest is schema 2 with `hierarchy_version: 2`; the execution-state
container remains schema 1. A future Gate D migration records
`previous_manifest_sha256`, `hierarchy_version`, and an append-only
`migration_history` entry only after the published Gate C repository evidence
has been read back. It preserves all prior attempts, failures, adoption
history, repository/project evidence, and empty Gate D collections. It never
resets or rewrites state and atomically replaces the state only after the new
manifest and hierarchy records validate. This local documentation change does
not modify the current ignored state file.

The migration operation below is documented but must not be run during this
local remediation. It is permitted only after the hierarchy migration commit
has been pushed normally and both local and remote main have been read back.
It is additive, atomic, and idempotent:

```bash
ig_migrate_state_after_remote_readback() {
  uv run --locked python - "$IG_MANIFEST_FILE" "$IG_STATE_FILE" "$IG_REPO" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

manifest_path, state_path = map(Path, sys.argv[1:3])
repository = sys.argv[3]
state = json.loads(state_path.read_text(encoding="utf-8"))
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
old_sha = "c8c1966a7d512f284bc9a96833b50cfa383b6c06ca30f54cb4401df40f335ed8"
old_state_bytes_sha = "b0c2623747a30c618d6ac68d2151b52c374feb5762d4c6b1b1ee5ffc3e0e964f"
new_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
if state.get("schema_version") != 1 or state.get("state_reset", False):
    raise SystemExit("state migration schema/reset precondition failed")
if state.get("manifest_sha256") not in {old_sha, new_sha}:
    raise SystemExit("unexpected previous manifest checksum")
if any(state.get(section) for section in ("milestone", "labels", "issues", "hierarchy", "project_items", "fields", "views")):
    raise SystemExit("Gate D collections must be empty for first migration")
if len(state.get("attempt_history", [])) != 18 or len(state.get("failure_history", [])) != 3:
    raise SystemExit("Gate C history is incomplete")
local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
remote_line = subprocess.check_output(["git", "ls-remote", repository, "refs/heads/main"], text=True).strip()
remote_sha = remote_line.split()[0] if remote_line else ""
if not local_sha or local_sha != remote_sha:
    raise SystemExit("local and remote migration commit do not match")
if state.get("manifest_sha256") == new_sha:
    history = state.get("migration_history", [])
    if any(row.get("migration_id") == "hierarchy-v2" and row.get("commit_sha") == local_sha for row in history):
        raise SystemExit(0)
    raise SystemExit("conflicting hierarchy-v2 migration replay")
if hashlib.sha256(state_path.read_bytes()).hexdigest() != old_state_bytes_sha:
    raise SystemExit("unexpected pre-migration execution-state checksum")
state["hierarchy_version"] = 2
state["manifest_sha256"] = new_sha
state["state_reset"] = False
state.setdefault("migration_history", []).append({
    "migration_id": "hierarchy-v2",
    "from_manifest_sha256": old_sha,
    "to_manifest_sha256": new_sha,
    "commit_sha": local_sha,
    "verified": True,
    "state_reset": False,
})
state["state_sha256"] = ""
canonical_state = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
state["state_sha256"] = hashlib.sha256(canonical_state).hexdigest()
temporary = state_path.with_name(f".{state_path.name}.migration.tmp")
try:
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    json.loads(temporary.read_text(encoding="utf-8"))
    os.replace(temporary, state_path)
finally:
    temporary.unlink(missing_ok=True)
json.loads(state_path.read_text(encoding="utf-8"))
written = json.loads(state_path.read_text(encoding="utf-8"))
stored = written["state_sha256"]
written["state_sha256"] = ""
actual = hashlib.sha256(json.dumps(written, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if stored != actual:
    raise SystemExit("post-migration state checksum mismatch")
PY
}

# Invoke only after a separately approved migration commit and remote read-back:
# ig_migrate_state_after_remote_readback
```

## 4. Atomic state helper — LOCAL WRITE, Gate C/D evidence

Define this function once in the same shell. It uses only Python's standard
library, validates existing and new JSON, writes beside the state, calls
`os.replace`, rejects unknown operations, and never prints state or secrets.

```bash
ig_state() {
  local state_operation="$1"
  shift
  uv run --locked python - "$IG_STATE_FILE" "$state_operation" "$@" <<'PY'
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

state_path = Path(sys.argv[1])
operation = sys.argv[2]
args = sys.argv[3:]
if not state_path.is_file():
    raise SystemExit("execution state is missing")
try:
    state = json.loads(state_path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"invalid execution state: {exc}") from exc
if state.get("schema_version") != 1:
    raise SystemExit("unsupported execution-state schema")

def require(count):
    if len(args) != count:
        raise SystemExit(f"{operation} requires {count} arguments")

def object_arg(raw):
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("state record must be a JSON object")
    return value

def clean_error(value):
    value = re.sub(r"(?i)(authorization|token|bearer|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b", "[REDACTED]", value)
    return value.replace("\x00", "")[:2000]

def manifest_document():
    path = Path(state["manifest_path"])
    document = json.loads(path.read_text(encoding="utf-8"))
    if sha256(path.read_bytes()).hexdigest() != state["manifest_sha256"]:
        raise SystemExit("manifest checksum changed during execution")
    return document

def expected_view_properties(view):
    directions = {
        "MVP Board": ["field-option-order", "ascending"],
        "Full Backlog": ["field-option-order", "ascending", "ascending"],
        "Umbrella Progress": ["ascending"],
    }
    normalized_filter = "no-active-filter" if view["name"] == "Full Backlog" else view["filter"]
    return {
        "name": view["name"],
        "layout": view["layout"],
        "filter": normalized_filter,
        "columns": view.get("columns", []),
        "group_by": view.get("group_by"),
        "sort": view.get("sort", []),
        "sort_directions": directions[view["name"]],
    }

def valid_utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None

def validate_verified_view(key, record, manifest):
    views = {view["name"]: view for view in manifest["project"]["views"]}
    if key not in views or record.get("manifest_identifier") != key or record.get("view_name") != key:
        raise SystemExit("view manifest identity mismatch")
    mandatory = {
        "resource_type", "manifest_identifier", "view_name", "remote_view_id",
        "remote_view_url", "project_id", "project_url", "source",
        "expected_properties", "observed_properties", "verification_method",
        "verified_by", "verification_timestamp", "attestation_reference",
        "verified", "manual_required", "ui_evidence", "screenshot_evidence",
    }
    if mandatory - record.keys():
        raise SystemExit(f"incomplete verified view record: {key}")
    if record["resource_type"] != "project-view" or record["source"] not in {
        "project-default-manually-configured", "manual-ui-created"
    }:
        raise SystemExit(f"invalid verified view source: {key}")
    if not record["remote_view_id"] or not record["remote_view_url"]:
        raise SystemExit(f"verified view lacks remote identity: {key}")
    if record["project_id"] != state["project"].get("id") or record["project_url"] != state["project"].get("url"):
        raise SystemExit(f"verified view Project identity mismatch: {key}")
    expected = expected_view_properties(views[key])
    if record["expected_properties"] != expected or record["observed_properties"] != expected:
        raise SystemExit(f"verified view properties mismatch: {key}")
    if record["verification_method"] != "authenticated-github-ui" or record["verified_by"] != manifest["repository"]["owner"]:
        raise SystemExit(f"verified view lacks authenticated UI identity: {key}")
    if not valid_utc_timestamp(record["verification_timestamp"]):
        raise SystemExit(f"verified view timestamp is invalid: {key}")
    attestation = "I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md."
    if record["attestation_reference"] != attestation:
        raise SystemExit(f"verified view attestation mismatch: {key}")
    if record["verified"] is not True or record["manual_required"] is not False:
        raise SystemExit(f"view is not fully verified: {key}")
    evidence = record["ui_evidence"]
    required_evidence = {
        "authenticated_account_verified", "project_identity_verified",
        "view_identity_verified", "name_verified", "layout_verified",
        "filter_verified", "visible_fields_verified", "group_by_verified",
        "sort_verified", "exact_view_set_verified", "inspection_completed",
    }
    if not isinstance(evidence, dict) or required_evidence - evidence.keys():
        raise SystemExit(f"view UI evidence is incomplete: {key}")
    if any(evidence[field] is not True for field in required_evidence):
        raise SystemExit(f"view UI evidence is not fully verified: {key}")
    if evidence.get("screenshot_only") is not False or not evidence.get("inspection_reference"):
        raise SystemExit(f"screenshot-only or unidentified UI evidence: {key}")
    screenshots = record["screenshot_evidence"]
    if not isinstance(screenshots, list) or any(
        not isinstance(item, dict) or not item.get("description") or
        len(item.get("sha256", "")) != 64 or
        any(character not in "0123456789abcdef" for character in item["sha256"])
        for item in screenshots
    ):
        raise SystemExit(f"invalid optional screenshot evidence: {key}")

def validate_pending_view(key, record, manifest):
    required = {
        "resource_type", "manifest_identifier", "view_name", "project_id",
        "project_url", "remote_view_id", "remote_view_url", "source",
        "expected_properties", "status", "verified", "manual_required",
        "recorded_at",
    }
    allowed = required | {"original_remote_name"}
    if required - record.keys() or record.keys() - allowed:
        raise SystemExit(f"pending view record is incomplete or has unknown fields: {key}")
    views = {view["name"]: view for view in manifest["project"]["views"]}
    if key not in views or record["manifest_identifier"] != key or record["view_name"] != key:
        raise SystemExit("pending view manifest identity mismatch")
    if record["resource_type"] != "project-view" or record["status"] != "manual-pending":
        raise SystemExit("pending view record type or status is invalid")
    if record["project_id"] != state["project"].get("id") or record["project_url"] != state["project"].get("url"):
        raise SystemExit("pending view Project identity mismatch")
    if record["expected_properties"] != expected_view_properties(views[key]):
        raise SystemExit("pending view expected properties differ from the manifest")
    if record["verified"] is not False or record["manual_required"] is not True:
        raise SystemExit("pending view cannot be verified or non-manual")
    if not valid_utc_timestamp(record["recorded_at"]):
        raise SystemExit("pending view timestamp is invalid")
    remote_id = record["remote_view_id"]
    remote_url = record["remote_view_url"]
    if bool(remote_id) != bool(remote_url):
        raise SystemExit("pending view remote ID and URL must be present together")
    if record["source"] == "project-creation-side-effect":
        if key != "MVP Board" or not remote_id or not remote_url:
            raise SystemExit("default Project view must be reserved for MVP Board")
        if "original_remote_name" not in record or not isinstance(record["original_remote_name"], str):
            raise SystemExit("default Project view lacks its original remote name")
    elif record["source"] == "manual-ui-required":
        if remote_id is not None or remote_url is not None or "original_remote_name" in record:
            raise SystemExit("uncreated manual view cannot have a remote identity")
    else:
        raise SystemExit("pending view source is invalid")

def canonical_pending_view(record):
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def validate_view_collection(manifest):
    manifest_identifiers = set()
    view_names = set()
    remote_ids = set()
    for state_key, existing_record in state["views"].items():
        if not isinstance(existing_record, dict):
            raise SystemExit("view state contains a non-object record")
        if existing_record.get("verified") is True:
            validate_verified_view(state_key, existing_record, manifest)
        else:
            validate_pending_view(state_key, existing_record, manifest)
        manifest_identifier = existing_record["manifest_identifier"]
        view_name = existing_record["view_name"]
        remote_id = existing_record.get("remote_view_id")
        if manifest_identifier in manifest_identifiers or view_name in view_names:
            raise SystemExit("duplicate manifest identifier or view name in state")
        if remote_id and remote_id in remote_ids:
            raise SystemExit("duplicate remote view ID in state")
        manifest_identifiers.add(manifest_identifier)
        view_names.add(view_name)
        if remote_id:
            remote_ids.add(remote_id)

if operation == "set-scalar":
    require(2)
    field, raw = args
    protected = {"schema_version", "manifest_path", "manifest_sha256", "last_verified_operation", "failed_operation", "error", "completed", "finalized_at", "state_sha256"}
    if field not in state or field in protected or isinstance(state[field], (dict, list)):
        raise SystemExit("invalid scalar field")
    state[field] = json.loads(raw)
elif operation in {"repository", "milestone", "project", "fields"}:
    require(1)
    state[operation] = object_arg(args[0])
elif operation in {"label", "issue", "hierarchy", "project-item"}:
    require(2)
    key, raw = args
    section = {"label": "labels", "issue": "issues", "hierarchy": "hierarchy", "project-item": "project_items"}[operation]
    if not key:
        raise SystemExit("state record key is empty")
    state[section][key] = object_arg(raw)
elif operation == "manual-view-pending":
    require(2)
    key, raw = args
    record = object_arg(raw)
    manifest = manifest_document()
    validate_view_collection(manifest)
    validate_pending_view(key, record, manifest)
    existing = state["views"].get(key)
    if existing is not None:
        if existing.get("verified") is True:
            raise SystemExit("cannot downgrade a verified view to pending")
        if canonical_pending_view(existing) == canonical_pending_view(record):
            raise SystemExit(0)
        raise SystemExit("conflicting pending view record; stored identity is immutable")
    if any(other.get("manifest_identifier") == record["manifest_identifier"] for other in state["views"].values()):
        raise SystemExit("duplicate pending manifest identifier")
    if any(other.get("view_name") == record["view_name"] for other in state["views"].values()):
        raise SystemExit("duplicate pending view name")
    remote_id = record.get("remote_view_id")
    if remote_id and any(
        other.get("remote_view_id") == remote_id for other in state["views"].values()
    ):
        raise SystemExit("duplicate pending remote view ID")
    state["views"][key] = record
    validate_view_collection(manifest)
elif operation == "manual-view-verified":
    require(2)
    key, raw = args
    record = object_arg(raw)
    manifest = manifest_document()
    validate_view_collection(manifest)
    pending = state["views"].get(key)
    if not isinstance(pending, dict) or pending.get("status") != "manual-pending":
        raise SystemExit("verified view lacks its pending lifecycle record")
    expected_source = "project-default-manually-configured" if pending.get("source") == "project-creation-side-effect" else "manual-ui-created"
    if record.get("source") != expected_source:
        raise SystemExit("verified view source contradicts its pending lifecycle")
    if record.get("manifest_identifier") != pending.get("manifest_identifier") or record.get("view_name") != pending.get("view_name"):
        raise SystemExit("verified view identity differs from pending state")
    if record.get("project_id") != pending.get("project_id") or record.get("project_url") != pending.get("project_url"):
        raise SystemExit("verified view Project identity differs from pending state")
    if record.get("expected_properties") != pending.get("expected_properties"):
        raise SystemExit("verified view expected properties differ from pending state")
    if pending.get("remote_view_id") and (
        record.get("remote_view_id") != pending.get("remote_view_id") or
        record.get("remote_view_url") != pending.get("remote_view_url")
    ):
        raise SystemExit("default view remote identity changed during manual configuration")
    validate_verified_view(key, record, manifest)
    if any(
        other_key != key and other.get("remote_view_id") == record["remote_view_id"]
        for other_key, other in state["views"].items()
    ):
        raise SystemExit("duplicate verified remote view ID")
    state["views"][key] = record
    validate_view_collection(manifest)
elif operation == "adoption-required":
    require(5)
    resource_type, manifest_identifier, remote_identifier, expected_raw, observed_raw = args
    if state.get("adoption_required") is not None:
        raise SystemExit("another adoption is already required")
    if not resource_type or not manifest_identifier or not remote_identifier:
        raise SystemExit("adoption identity is incomplete")
    state["adoption_required"] = {
        "resource_type": resource_type,
        "manifest_identifier": manifest_identifier,
        "remote_identifier": remote_identifier,
        "expected_properties": object_arg(expected_raw),
        "observed_properties": object_arg(observed_raw),
        "approval_reference": None,
        "approval_timestamp": None,
        "source": "unowned_remote",
        "verified": False,
        "verification_timestamp": None,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
elif operation in {"adopt-label", "adopt-project-link"}:
    require(2 if operation == "adopt-label" else 1)
    key = args[0] if operation == "adopt-label" else None
    record = object_arg(args[1] if operation == "adopt-label" else args[0])
    required = state.get("adoption_required")
    if not isinstance(required, dict):
        raise SystemExit("no active adoption-required condition")
    mandatory = {
        "resource_type", "manifest_identifier", "remote_identifier",
        "expected_properties", "observed_properties", "approval_reference",
        "approval_timestamp", "source", "verified", "verification_timestamp",
    }
    if mandatory - record.keys():
        raise SystemExit("adoption record is incomplete")
    if record["source"] != "adopted" or record["verified"] is not True:
        raise SystemExit("adoption record must be adopted and verified")
    if not record["approval_reference"] or not record["approval_timestamp"]:
        raise SystemExit("adoption approval is missing")
    for field in ("resource_type", "manifest_identifier", "remote_identifier", "expected_properties", "observed_properties"):
        if record[field] != required.get(field):
            raise SystemExit(f"adoption record differs from required {field}")
    if operation == "adopt-label":
        if record["resource_type"] != "label" or key != record["manifest_identifier"]:
            raise SystemExit("label adoption identity mismatch")
        state["labels"][key] = record
    else:
        if record["resource_type"] != "repository-project-link":
            raise SystemExit("Project-link adoption type mismatch")
        if not state.get("project"):
            raise SystemExit("Project state is missing")
        state["project"]["linked_repository"] = record
    state["adoption_history"].append(record)
    state["adoption_required"] = None
elif operation == "attempt":
    require(1)
    history = state.setdefault("attempt_history", [])
    if not isinstance(history, list):
        raise SystemExit("attempt history is invalid")
    history.append({
        "operation": args[0],
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "runbook",
    })
    state["last_attempted_operation"] = args[0]
elif operation == "verified":
    require(1)
    state["last_verified_operation"] = args[0]
    state["failed_operation"] = None
    state["error"] = None
elif operation == "failure":
    require(3)
    op_name, exit_code, message = args
    failure = {"operation": op_name, "exit_code": int(exit_code), "message": clean_error(message)}
    state["failed_operation"] = op_name
    state["error"] = failure
    state["failure_history"].append({
        **failure,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })
elif operation == "finalize":
    require(1)
    manifest_path = Path(state["manifest_path"])
    current_manifest_hash = sha256(manifest_path.read_bytes()).hexdigest()
    if current_manifest_hash != state["manifest_sha256"]:
        raise SystemExit("manifest checksum changed during execution")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {"labels": 16, "issues": 34, "hierarchy": 31, "project_items": 34, "views": 3}
    for section, count in expected.items():
        if len(state[section]) != count:
            raise SystemExit(f"incomplete {section}: {len(state[section])}/{count}")
    if state["failed_operation"] is not None or state["error"] is not None:
        raise SystemExit("cannot finalize with a current failure")
    if state.get("adoption_required") is not None:
        raise SystemExit("cannot finalize while adoption is required")
    if state.get("last_verified_operation") != "final-read-only-verification":
        raise SystemExit("final remote read-back has not been verified")
    if not state["repository"].get("verified") or not state["milestone"].get("verified") or not state["project"].get("verified"):
        raise SystemExit("repository, M1 milestone, or Project is not verified")
    if not state["fields"].get("verified"):
        raise SystemExit("Project fields are not verified")
    for section in ("labels", "issues", "hierarchy", "project_items"):
        if any(not record.get("verified") for record in state[section].values()):
            raise SystemExit(f"unverified record in {section}")
    manifest_labels = {row["name"] for row in manifest["labels"]}
    if len(manifest_labels) != 16 or set(state["labels"]) != manifest_labels:
        raise SystemExit("managed label state does not exactly match the manifest")
    expected_label_records = {row["name"]: row for row in manifest["labels"]}
    for name, record in state["labels"].items():
        manifest_record = expected_label_records[name]
        expected_properties = {
            "name": name,
            "color": manifest_record["color"].upper(),
            "description": manifest_record["description"],
        }
        if record.get("source") not in {"created", "adopted"}:
            raise SystemExit(f"invalid label source: {name}")
        if record.get("verified") is not True or record.get("expected_properties") != expected_properties:
            raise SystemExit(f"label state differs from manifest: {name}")
        if record.get("observed_properties") != expected_properties:
            raise SystemExit(f"label state lacks exact read-back: {name}")
        if record.get("source") == "adopted" and not record.get("approval_reference"):
            raise SystemExit(f"adopted label lacks approval: {name}")
    link = state["project"].get("linked_repository")
    if not isinstance(link, dict) or link.get("source") not in {"created", "adopted"} or link.get("verified") is not True:
        raise SystemExit("repository-Project link state is incomplete")
    if link.get("source") == "adopted" and not link.get("approval_reference"):
        raise SystemExit("adopted repository-Project link lacks approval")
    expected_repo = manifest["repository"]
    expected_link_properties = {
        "repository_owner": expected_repo["owner"],
        "repository_name": expected_repo["name"],
        "repository_name_with_owner": f'{expected_repo["owner"]}/{expected_repo["name"]}',
        "repository_id": state["repository"].get("id"),
        "project_number": state["project"].get("number"),
        "project_id": state["project"].get("id"),
        "project_title": manifest["project"]["title"],
    }
    if link.get("expected_properties") != expected_link_properties or link.get("observed_properties") != expected_link_properties:
        raise SystemExit("repository-Project link properties differ from managed identities")
    adopted_records = [record for record in state["labels"].values() if record.get("source") == "adopted"]
    if link.get("source") == "adopted":
        adopted_records.append(link)
    history = state.get("adoption_history")
    if not isinstance(history, list):
        raise SystemExit("adoption history is invalid")
    canonical_history = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in history]
    canonical_adopted = [json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for record in adopted_records]
    if sorted(canonical_history) != sorted(canonical_adopted):
        raise SystemExit("adoption history differs from adopted managed resources")
    manifest_views = {view["name"]: view for view in manifest["project"]["views"]}
    if len(manifest_views) != 3 or set(state["views"]) != set(manifest_views):
        raise SystemExit("view state does not exactly match the three manifest views")
    for name, record in state["views"].items():
        validate_verified_view(name, record, manifest)
    remote_ids = [record["remote_view_id"] for record in state["views"].values()]
    if len(set(remote_ids)) != 3:
        raise SystemExit("verified view remote IDs are not unique")
    state["completed"] = True
    state["finalized_at"] = args[0]
    state["last_verified_operation"] = "final-read-only-verification"
    state["state_sha256"] = ""
    canonical = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    state["state_sha256"] = sha256(canonical).hexdigest()
else:
    raise SystemExit(f"invalid state operation: {operation}")

handle = tempfile.NamedTemporaryFile(
    mode="w", encoding="utf-8", dir=state_path.parent,
    prefix=".github-execution-state.", suffix=".tmp", delete=False,
)
temporary = Path(handle.name)
try:
    with handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    json.loads(temporary.read_text(encoding="utf-8"))
    os.replace(temporary, state_path)
finally:
    if temporary.exists():
        temporary.unlink()
json.loads(state_path.read_text(encoding="utf-8"))
PY
}

ig_state_entry() {
  local section="$1"
  local key="$2"
  uv run --locked python - "$IG_STATE_FILE" "$section" "$key" <<'PY'
import json
import sys
from pathlib import Path
state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
section, key = sys.argv[2], sys.argv[3]
section_value = state.get(section, {})
if section in {"repository", "project"} and key == "primary":
    value = section_value or None
else:
    value = section_value.get(key)
if value is not None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
PY
}
```

The `manual-view-pending` and `manual-view-verified` operations update only the
named `views` entry. A separate `verified` operation may update the normal
operation markers after read-back succeeds. Both paths preserve schema version
1, every Gate C evidence field, and all append-only attempt, failure, and
adoption history; they reject incomplete, duplicate, or contradictory view
records before the atomic replacement. A repeated pending payload is
idempotent only when its complete validated canonical JSON object is identical
to the stored pending record. That exact match exits successfully before a
temporary file is opened, so state bytes and checksums remain unchanged. Any
difference—including Project identity, expected properties, source, view name,
or an already bound remote identity—is a nonzero conflict and cannot replace
the stored record. A remote identity may first be bound to an unbound pending
record only through `manual-view-verified`. Before either operation, the helper
validates the complete view collection: manifest identifiers and view names
must be unique, every non-empty remote view ID must be unique, and every record
must retain the state-owned Project ID and URL.

## 5. Failure-recording and verification wrappers

The wrapper records the attempted operation, captures stdout and stderr in
separate task-specific files, sanitizes the error, records the exit code, and
returns non-zero. It does not rely on an `ERR` trap. The caller must stop on a
non-zero return. Successful mutation is not enough: `ig_verify_operation`
marks it verified and clears the current failure only after read-back succeeds.

```bash
ig_sanitized_error() {
  uv run --locked python - "$1" <<'PY'
import re
import sys
from pathlib import Path
value = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
value = re.sub(r"(?i)(authorization|token|bearer|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b", "[REDACTED]", value)
print(value.replace("\x00", "")[:2000])
PY
}

ig_run_mutation() {
  local operation="$1"
  shift
  IG_CURRENT_OPERATION="$operation"
  ig_state attempt "$operation"
  : > "$IG_MUTATION_STDOUT"
  : > "$IG_MUTATION_STDERR"
  if "$@" >"$IG_MUTATION_STDOUT" 2>"$IG_MUTATION_STDERR"; then
    return 0
  else
    local command_status=$?
  fi
  local safe_error
  safe_error="$(ig_sanitized_error "$IG_MUTATION_STDERR")"
  ig_state failure "$operation" "$command_status" "$safe_error"
  return "$command_status"
}

ig_verify_operation() {
  local operation="$1"
  shift
  : > "$IG_MUTATION_STDOUT"
  : > "$IG_MUTATION_STDERR"
  if "$@" >"$IG_MUTATION_STDOUT" 2>"$IG_MUTATION_STDERR"; then
    ig_state verified "$operation"
    return 0
  else
    local verify_status=$?
  fi
  local safe_error
  safe_error="$(ig_sanitized_error "$IG_MUTATION_STDERR")"
  test -n "$safe_error" || safe_error='read-back verification failed'
  ig_state failure "$operation" "$verify_status" "$safe_error"
  return "$verify_status"
}
```

## 6. Gate C repository, push, and metadata

### 6.1 Repository creation — REMOTE WRITE, Gate C

Check state first. If no repository is recorded, an existing exact remote
repository is an unrecorded match and requires explicit adoption. Creation and
push remain separate visible mutations.

```bash
ig_verify_repository_identity() {
  local repository_id="$1" remote_url="$2"
  local payload
  payload="$(gh repo view "$IG_REPO" --json id,nameWithOwner,visibility,url,sshUrl)"
  uv run --locked python - "$payload" "$IG_REPO" "$repository_id" "$remote_url" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("nameWithOwner")!=sys.argv[2] or d.get("id")!=sys.argv[3] or d.get("sshUrl")!=sys.argv[4] or d.get("visibility")!="PUBLIC":
    raise SystemExit("repository state read-back mismatch")
PY
}

ig_repo_state="$(ig_state_entry repository primary)"
if test -n "$ig_repo_state"; then
  IG_REPOSITORY_ID="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ig_repo_state")"
  IG_REMOTE_URL="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["ssh_url"])' "$ig_repo_state")"
  ig_verify_operation '06-reuse-repository' ig_verify_repository_identity "$IG_REPOSITORY_ID" "$IG_REMOTE_URL" || exit 1
else
  ig_remote_matches="$(gh repo list "$IG_OWNER" --limit 1000 --json name,nameWithOwner,visibility,url | uv run --locked python -c 'import json,sys; rows=json.load(sys.stdin); print(sum(row["nameWithOwner"]==sys.argv[1] for row in rows))' "$IG_REPO")"
  test "$ig_remote_matches" -eq 0 || { printf '%s\n' 'STOP: unrecorded matching repository requires explicit adoption.' >&2; exit 1; }
  ig_run_mutation '06-create-repository' gh repo create "$IG_REPO" --public || exit 1
  ig_repository_json="$(gh repo view "$IG_REPO" --json id,nameWithOwner,visibility,url,sshUrl)"
  ig_repo_record="$(uv run --locked python - "$ig_repository_json" <<'PY'
import json, sys
d=json.loads(sys.argv[1])
print(json.dumps({"id":d["id"],"url":d["url"],"ssh_url":d["sshUrl"],"verified":False},separators=(",",":")))
PY
)"
  ig_state repository "$ig_repo_record"
  IG_REPOSITORY_ID="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ig_repo_record")"
  IG_REMOTE_URL="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["ssh_url"])' "$ig_repo_record")"
  ig_verify_operation '06-create-repository' ig_verify_repository_identity "$IG_REPOSITORY_ID" "$IG_REMOTE_URL" || exit 1
  ig_repo_record="$(uv run --locked python - "$ig_repo_record" <<'PY'
import json,sys
d=json.loads(sys.argv[1]); d["verified"]=True
print(json.dumps(d,separators=(",",":")))
PY
)"
  ig_state repository "$ig_repo_record"
fi
test -n "$IG_REPOSITORY_ID"
test -n "$IG_REMOTE_URL"
```

### 6.2 Reviewed main push — LOCAL WRITE and REMOTE WRITE, Gate C

```bash
test "$(git rev-parse --is-inside-work-tree)" = 'true'
test "$(git branch --show-current)" = 'main'
test -z "$(git status --short)"
IG_LOCAL_HEAD="$(git rev-parse HEAD)"
test -n "$IG_LOCAL_HEAD"
ig_verify_main_push() {
  IG_REMOTE_HEAD="$(git ls-remote --heads origin refs/heads/main | awk '{print $1}')"
  test "$IG_REMOTE_HEAD" = "$IG_LOCAL_HEAD"
}
if git remote get-url origin >/dev/null 2>&1; then
  test "$(git remote get-url origin)" = "$IG_REMOTE_URL"
else
  git remote add origin "$IG_REMOTE_URL"
  test "$(git remote get-url origin)" = "$IG_REMOTE_URL"
fi
IG_REMOTE_HEAD="$(git ls-remote --heads origin refs/heads/main | awk '{print $1}')"
if test -z "$IG_REMOTE_HEAD"; then
  ig_run_mutation '06-push-reviewed-main' git push -u origin main || exit 1
elif test "$IG_REMOTE_HEAD" != "$IG_LOCAL_HEAD"; then
  printf '%s\n' 'STOP: remote main exists at a different commit; do not force or overwrite it.' >&2
  exit 1
fi
ig_verify_operation '06-push-reviewed-main' ig_verify_main_push || exit 1
ig_repo_state="$(ig_state_entry repository primary)"
ig_repository_url="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["url"])' "$ig_repo_state")"
ig_repo_record="$(uv run --locked python - "$IG_REPOSITORY_ID" "$ig_repository_url" "$IG_REMOTE_URL" "$IG_LOCAL_HEAD" <<'PY'
import json,sys
print(json.dumps({"id":sys.argv[1],"url":sys.argv[2],"ssh_url":sys.argv[3],"main_commit":sys.argv[4],"verified":True},separators=(",",":")))
PY
)"
ig_state repository "$ig_repo_record"
```

### 6.3 Settings and topics — REMOTE WRITE, Gate C

```bash
ig_verify_repository_settings() {
  local payload
  payload="$(gh repo view "$IG_REPO" --json nameWithOwner,visibility,description,hasIssuesEnabled,hasProjectsEnabled,hasWikiEnabled,repositoryTopics,url)"
  uv run --locked python - "$payload" "$IG_MANIFEST_FILE" <<'PY'
import json,sys
from pathlib import Path
actual=json.loads(sys.argv[1]); expected=json.loads(Path(sys.argv[2]).read_text())["repository"]
if actual["nameWithOwner"]!=f'{expected["owner"]}/{expected["name"]}' or actual["visibility"]!="PUBLIC": raise SystemExit("repository identity mismatch")
if actual["description"]!=expected["description"] or not actual["hasIssuesEnabled"] or not actual["hasProjectsEnabled"] or actual["hasWikiEnabled"]: raise SystemExit("repository settings mismatch")
PY
}

ig_verify_repository_topic() {
  local expected_topic="$1" payload
  payload="$(gh repo view "$IG_REPO" --json repositoryTopics)"
  uv run --locked python - "$payload" "$expected_topic" <<'PY'
import json,sys
topics=json.loads(sys.argv[1])["repositoryTopics"]
if topics and isinstance(topics[0],dict): topics=[row["name"] for row in topics]
if topics.count(sys.argv[2])!=1: raise SystemExit("topic read-back mismatch")
PY
}

ig_run_mutation '06-repository-settings' gh repo edit "$IG_REPO" --description "$IG_DESCRIPTION" --enable-issues --enable-projects --enable-wiki=false || exit 1
ig_verify_operation '06-repository-settings' ig_verify_repository_settings || exit 1
while IFS= read -r -d '' ig_topic; do
  ig_run_mutation "06-topic-${ig_topic}" gh repo edit "$IG_REPO" --add-topic "$ig_topic" || exit 1
  ig_verify_operation "06-topic-${ig_topic}" ig_verify_repository_topic "$ig_topic" || exit 1
done < <(uv run --locked python - "$IG_MANIFEST_FILE" <<'PY'
import json,sys
from pathlib import Path
for topic in json.loads(Path(sys.argv[1]).read_text())["repository"]["topics"]:
    sys.stdout.buffer.write(topic.encode()+b"\0")
PY
)
```

## 7. Gate D labels — REMOTE WRITE, Gate D

The loop processes the 16 manifest labels in array order and always consults
execution state before GitHub. A matching remote label is not owned merely
because its values match the manifest. If it is absent from state, the loop
records one adoption-required condition and stops. Approval and adoption are a
separate operation for that exact label; one approval cannot adopt several
labels.

```bash
ig_label_observation() {
  local label_list="$1" label_name="$2"
  uv run --locked python - "$label_list" "$label_name" <<'PY'
import json
import sys

rows = [row for row in json.loads(sys.argv[1]) if row["name"] == sys.argv[2]]
if len(rows) > 1:
    raise SystemExit("duplicate remote label names")
if rows:
    row = rows[0]
    print(json.dumps({
        "name": row["name"],
        "color": row["color"].upper(),
        "description": row["description"],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
PY
}

ig_verify_label() {
  local label_name="$1" label_color="$2" label_description="$3"
  local label_list
  label_list="$(gh label list --repo "$IG_REPO" --limit 100 --json name,color,description)"
  uv run --locked python - "$label_list" "$label_name" "$label_color" "$label_description" <<'PY'
import json,sys
rows=[row for row in json.loads(sys.argv[1]) if row["name"] == sys.argv[2]]
if len(rows) != 1 or rows[0]["color"].upper() != sys.argv[3].upper() or rows[0]["description"] != sys.argv[4]:
    raise SystemExit("label read-back mismatch")
PY
}

ig_verify_recorded_label() {
  local label_record="$1" label_name="$2" label_color="$3" label_description="$4"
  uv run --locked python - "$label_record" "$label_name" "$label_color" "$label_description" <<'PY'
import json
import sys

record = json.loads(sys.argv[1])
expected = {
    "name": sys.argv[2],
    "color": sys.argv[3].upper(),
    "description": sys.argv[4],
}
if record.get("resource_type") != "label" or record.get("manifest_identifier") != sys.argv[2]:
    raise SystemExit("recorded label identity mismatch")
if record.get("remote_identifier") != sys.argv[2] or record.get("verified") is not True:
    raise SystemExit("recorded label is not verified")
if record.get("source") not in {"created", "adopted"}:
    raise SystemExit("recorded label source is invalid")
if any(record.get(key) != value for key, value in expected.items()):
    raise SystemExit("recorded label properties differ from manifest")
if record.get("expected_properties") != expected or record.get("observed_properties") != expected:
    raise SystemExit("recorded label expected/observed properties differ")
if not record.get("verification_timestamp"):
    raise SystemExit("recorded label verification timestamp is missing")
if record["source"] == "adopted" and (
    not record.get("approval_reference") or not record.get("approval_timestamp")
):
    raise SystemExit("adopted label lacks explicit approval evidence")
PY
}

while IFS= read -r -d '' ig_label_row; do
  mapfile -d '' -t ig_label_values < <(ig_json_fields "$ig_label_row" name color description)
  test "${#ig_label_values[@]}" -eq 3
  ig_label_name="${ig_label_values[0]}"
  ig_label_color="${ig_label_values[1]}"
  ig_label_description="${ig_label_values[2]}"
  ig_label_operation="07-label-${ig_label_name}"
  ig_label_state="$(ig_state_entry labels "$ig_label_name")"

  # Case A: recorded labels are reused only after state and remote read-back agree.
  if test -n "$ig_label_state"; then
    ig_verify_recorded_label "$ig_label_state" "$ig_label_name" "$ig_label_color" "$ig_label_description" || exit 1
    ig_verify_operation "${ig_label_operation}-reuse" ig_verify_label "$ig_label_name" "$ig_label_color" "$ig_label_description" || exit 1
    continue
  fi

  ig_label_list="$(gh label list --repo "$IG_REPO" --limit 100 --json name,color,description)"
  ig_label_observed="$(ig_label_observation "$ig_label_list" "$ig_label_name")"
  ig_label_expected="$(uv run --locked python - "$ig_label_name" "$ig_label_color" "$ig_label_description" <<'PY'
import json
import sys
print(json.dumps({"name":sys.argv[1],"color":sys.argv[2].upper(),"description":sys.argv[3]},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"

  # Case B: absence in both state and GitHub authorizes creation under Gate D.
  if test -z "$ig_label_observed"; then
    ig_run_mutation "$ig_label_operation" gh label create "$ig_label_name" --repo "$IG_REPO" --color "$ig_label_color" --description "$ig_label_description" || exit 1
    ig_verify_operation "$ig_label_operation" ig_verify_label "$ig_label_name" "$ig_label_color" "$ig_label_description" || exit 1
    ig_label_record="$(uv run --locked python - "$ig_label_name" "$ig_label_color" "$ig_label_description" <<'PY'
import json
import sys
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
properties = {"name":sys.argv[1],"color":sys.argv[2].upper(),"description":sys.argv[3]}
print(json.dumps({
    "resource_type":"label", "manifest_identifier":sys.argv[1],
    "remote_identifier":sys.argv[1], "expected_properties":properties,
    "observed_properties":properties, "approval_reference":None,
    "approval_timestamp":None, "source":"created", "verified":True,
    "verification_timestamp":now, **properties,
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
    ig_state label "$ig_label_name" "$ig_label_record"
    ig_state verified "$ig_label_operation"
    continue
  fi

  # Case C: any unrecorded remote match is unowned, even when it is exact.
  if test "$ig_label_observed" = "$ig_label_expected"; then
    ig_state adoption-required label "$ig_label_name" "$ig_label_name" "$ig_label_expected" "$ig_label_observed"
    printf 'ADOPTION REQUIRED: label identity=%s observed=%s\n' "$ig_label_name" "$ig_label_observed" >&2
    printf 'STOP: obtain explicit approval and run only the dedicated label-adoption operation.\n' >&2
    exit 1
  fi
  ig_state attempt "${ig_label_operation}-conflict"
  ig_state failure "${ig_label_operation}-conflict" 1 "conflicting existing label ${ig_label_name}; no mutation performed"
  printf 'HARD STOP: conflicting label identity=%s expected=%s observed=%s\n' "$ig_label_name" "$ig_label_expected" "$ig_label_observed" >&2
  exit 1
done < <(ig_manifest_stream labels)
test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["labels"]))' "$IG_STATE_FILE")" -eq 16
```

After the loop stops on one exact unrecorded label, obtain approval for that
specific identity. The recommended phrase is: `I approve adoption of the
existing exact-match GitHub label <LABEL_NAME> for the IntentGuard Gate D
execution.` Then run this separate operation. It validates the active
adoption condition, fetches the manifest rather than Markdown, queries GitHub
twice, atomically records `source=adopted`, and only then permits the original
label loop to resume.

```bash
read -r -p 'Exact label name to adopt: ' IG_ADOPTION_LABEL_NAME
read -r -p 'Paste the explicit approval phrase: ' IG_LABEL_ADOPTION_APPROVAL_REFERENCE
test -n "$IG_ADOPTION_LABEL_NAME"
ig_expected_label_approval="I approve adoption of the existing exact-match GitHub label ${IG_ADOPTION_LABEL_NAME} for the IntentGuard Gate D execution."
test "$IG_LABEL_ADOPTION_APPROVAL_REFERENCE" = "$ig_expected_label_approval"

ig_label_row="$(uv run --locked python - "$IG_MANIFEST_FILE" "$IG_ADOPTION_LABEL_NAME" <<'PY'
import json
import sys
from pathlib import Path

rows = [row for row in json.loads(Path(sys.argv[1]).read_text())["labels"] if row["name"] == sys.argv[2]]
if len(rows) != 1:
    raise SystemExit("approved label is absent or duplicated in the manifest")
print(json.dumps(rows[0], ensure_ascii=False, sort_keys=True, separators=(",", ":")))
PY
)"
mapfile -d '' -t ig_label_values < <(ig_json_fields "$ig_label_row" name color description)
ig_label_name="${ig_label_values[0]}"; ig_label_color="${ig_label_values[1]}"; ig_label_description="${ig_label_values[2]}"
ig_label_expected="$(uv run --locked python - "$ig_label_name" "$ig_label_color" "$ig_label_description" <<'PY'
import json,sys
print(json.dumps({"name":sys.argv[1],"color":sys.argv[2].upper(),"description":sys.argv[3]},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
ig_adoption_required="$(uv run --locked python - "$IG_STATE_FILE" "$ig_label_name" <<'PY'
import json,sys
from pathlib import Path
required=json.loads(Path(sys.argv[1]).read_text()).get("adoption_required")
if not isinstance(required,dict) or required.get("resource_type")!="label" or required.get("manifest_identifier")!=sys.argv[2]:
    raise SystemExit("active adoption condition does not identify this label")
print(json.dumps(required,ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
ig_label_list="$(gh label list --repo "$IG_REPO" --limit 100 --json name,color,description)"
ig_label_observed="$(ig_label_observation "$ig_label_list" "$ig_label_name")"
test -n "$ig_label_observed"
test "$ig_label_observed" = "$ig_label_expected" || { printf '%s\n' 'HARD STOP: label changed after adoption was requested.' >&2; exit 1; }
ig_approval_timestamp="$(uv run --locked python -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"))')"
ig_label_adoption_record="$(uv run --locked python - "$ig_label_name" "$ig_label_expected" "$ig_label_observed" "$IG_LABEL_ADOPTION_APPROVAL_REFERENCE" "$ig_approval_timestamp" <<'PY'
import json,sys
record={
    "resource_type":"label", "manifest_identifier":sys.argv[1],
    "remote_identifier":sys.argv[1], "expected_properties":json.loads(sys.argv[2]),
    "observed_properties":json.loads(sys.argv[3]), "approval_reference":sys.argv[4],
    "approval_timestamp":sys.argv[5], "source":"adopted", "verified":True,
    "verification_timestamp":sys.argv[5], **json.loads(sys.argv[2]),
}
print(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
ig_state adopt-label "$ig_label_name" "$ig_label_adoption_record"
ig_verify_operation "07-adopt-label-${ig_label_name}" ig_verify_label "$ig_label_name" "$ig_label_color" "$ig_label_description" || exit 1
printf 'Verified adoption recorded for %s; restart the complete label loop.\n' "$ig_label_name"
```

## 8. Project creation and repository link — REMOTE WRITE, Gate D

An exact-title Project that is absent from state requires explicit adoption.
The creation result and public visibility are immediately read back. The same
creation read-back also inventories zero or one implicit default view. A
single view created as part of that exact Project mutation is recorded as a
Project-creation side effect and reserved for **MVP Board**; it is not an
adoption. More than one view, or a view first discovered on a later resume
without a state record, stops execution.

```bash
ig_verify_project_identity() {
  local require_public="$1"
  local payload
  payload="$(gh project view "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --format json)"
  uv run --locked python - "$payload" "$IG_PROJECT_TITLE" "$IG_PROJECT_ID" "$IG_PROJECT_URL" "$require_public" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("title")!=sys.argv[2] or d.get("id")!=sys.argv[3] or d.get("url")!=sys.argv[4]:
    raise SystemExit("Project identity read-back mismatch")
if sys.argv[5]=="true" and d.get("public") is not True:
    raise SystemExit("Project is not public")
PY
}

ig_read_views_request() {
  gh api -H "X-GitHub-Api-Version: ${IG_API_VERSION}" "$ig_views_endpoint"
}

ig_stream_remote_views() {
  local payload="$1"
  uv run --locked python - "$payload" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
rows = payload.get("views", payload if isinstance(payload, list) else [])
if not isinstance(rows, list):
    raise SystemExit("Project view listing has an unsupported shape")
seen = set()
for row in rows:
    remote_id = str(row.get("id") or row.get("node_id") or "")
    remote_url = str(row.get("html_url") or row.get("url") or "")
    if not remote_id or not remote_url or remote_id in seen:
        raise SystemExit("Project view listing has missing or duplicate identity")
    seen.add(remote_id)
    record = {"id": remote_id, "url": remote_url, "name": row.get("name") or ""}
    sys.stdout.buffer.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode() + b"\0")
PY
}

ig_project_created_now=0
ig_project_state="$(ig_state_entry project primary)"
if test -n "$ig_project_state"; then
  mapfile -d '' -t ig_project_values < <(ig_json_fields "$ig_project_state" number id url)
  IG_PROJECT_NUMBER="${ig_project_values[0]}"
  IG_PROJECT_ID="${ig_project_values[1]}"
  IG_PROJECT_URL="${ig_project_values[2]}"
  ig_verify_operation '08-reuse-project' ig_verify_project_identity false || exit 1
else
  ig_project_matches="$(gh project list --owner "$IG_OWNER" --limit 100 --format json | uv run --locked python -c 'import json,sys; print(sum(row["title"]==sys.argv[1] for row in json.load(sys.stdin)["projects"]))' "$IG_PROJECT_TITLE")"
  test "$ig_project_matches" -eq 0 || { printf '%s\n' 'STOP: unrecorded exact-title Project requires explicit adoption.' >&2; exit 1; }
  ig_run_mutation '08-create-project' gh project create --owner "$IG_OWNER" --title "$IG_PROJECT_TITLE" --format json || exit 1
  ig_project_json="$(cat "$IG_MUTATION_STDOUT")"
  mapfile -d '' -t ig_project_values < <(ig_json_fields "$ig_project_json" number id url)
  test "${#ig_project_values[@]}" -eq 3
  IG_PROJECT_NUMBER="${ig_project_values[0]}"
  IG_PROJECT_ID="${ig_project_values[1]}"
  IG_PROJECT_URL="${ig_project_values[2]}"
  test -n "$IG_PROJECT_NUMBER"; test -n "$IG_PROJECT_ID"; test -n "$IG_PROJECT_URL"
  ig_verify_operation '08-create-project' ig_verify_project_identity false || exit 1
  ig_project_record="$(uv run --locked python - "$IG_PROJECT_NUMBER" "$IG_PROJECT_ID" "$IG_PROJECT_URL" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"public":False,"linked_repository":None,"source":"created","creation_operation":"08-create-project","verified":True},separators=(",",":")))
PY
)"
  ig_state project "$ig_project_record"
  ig_project_created_now=1
fi
test -n "$IG_PROJECT_NUMBER"; test -n "$IG_PROJECT_ID"; test -n "$IG_PROJECT_URL"

# Capture the implicit default view only during the direct read-back of the
# Project mutation. A later unrecorded remote view is unowned and requires an
# explicit, resource-specific adoption decision.
ig_views_endpoint="users/${IG_OWNER_ID}/projectsV2/${IG_PROJECT_NUMBER}/views"
if test "$IG_OWNER_TYPE" = 'Organization'; then
  ig_views_endpoint="orgs/${IG_OWNER}/projectsV2/${IG_PROJECT_NUMBER}/views"
fi
ig_remote_views_json="$(ig_read_views_request)"
mapfile -d '' -t ig_remote_view_rows < <(ig_stream_remote_views "$ig_remote_views_json")
ig_mvp_view_state="$(ig_state_entry views 'MVP Board')"
if test "$ig_project_created_now" -eq 1; then
  test -z "$ig_mvp_view_state"
  test "${#ig_remote_view_rows[@]}" -le 1 || { printf '%s\n' 'HARD STOP: Project creation returned more than one unexpected view.' >&2; exit 1; }
  if test "${#ig_remote_view_rows[@]}" -eq 1; then
    mapfile -d '' -t ig_default_view_values < <(ig_json_fields "${ig_remote_view_rows[0]}" id url name)
    ig_default_view_record="$(uv run --locked python - "$IG_MANIFEST_FILE" "$IG_PROJECT_ID" "$IG_PROJECT_URL" "${ig_default_view_values[0]}" "${ig_default_view_values[1]}" "${ig_default_view_values[2]}" <<'PY'
import json,sys
from datetime import datetime,timezone
from pathlib import Path
manifest=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
view=next(row for row in manifest["project"]["views"] if row["name"]=="MVP Board")
expected={
    "name":view["name"], "layout":view["layout"], "filter":view["filter"],
    "columns":view.get("columns",[]), "group_by":view.get("group_by"),
    "sort":view.get("sort",[]), "sort_directions":["field-option-order","ascending"],
}
print(json.dumps({
    "resource_type":"project-view", "manifest_identifier":"MVP Board",
    "view_name":"MVP Board", "project_id":sys.argv[2], "project_url":sys.argv[3],
    "remote_view_id":sys.argv[4], "remote_view_url":sys.argv[5],
    "original_remote_name":sys.argv[6], "source":"project-creation-side-effect",
    "expected_properties":expected,
    "status":"manual-pending", "verified":False, "manual_required":True,
    "recorded_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
    ig_state manual-view-pending 'MVP Board' "$ig_default_view_record"
  fi
elif test -n "$ig_mvp_view_state"; then
  ig_recorded_default_id="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1]).get("remote_view_id") or "")' "$ig_mvp_view_state")"
  if test -n "$ig_recorded_default_id"; then
    test "$(uv run --locked python - "$ig_remote_views_json" "$ig_recorded_default_id" <<'PY'
import json,sys
payload=json.loads(sys.argv[1]); rows=payload.get("views",payload if isinstance(payload,list) else [])
print(sum(str(row.get("id") or row.get("node_id") or "")==sys.argv[2] for row in rows))
PY
)" -eq 1 || { printf '%s\n' 'STOP: recorded default view identity no longer matches the Project.' >&2; exit 1; }
  fi
elif test "${#ig_remote_view_rows[@]}" -ne 0; then
  test "${#ig_remote_view_rows[@]}" -eq 1 || { printf '%s\n' 'HARD STOP: multiple unrecorded Project views exist.' >&2; exit 1; }
  mapfile -d '' -t ig_unowned_view_values < <(ig_json_fields "${ig_remote_view_rows[0]}" id url name)
  ig_unowned_expected="$(uv run --locked python - "$IG_PROJECT_ID" "$IG_PROJECT_URL" <<'PY'
import json,sys
print(json.dumps({"project_id":sys.argv[1],"project_url":sys.argv[2],"reserved_target":"MVP Board"},sort_keys=True,separators=(",",":")))
PY
)"
  ig_unowned_observed="$(uv run --locked python - "${ig_unowned_view_values[0]}" "${ig_unowned_view_values[1]}" "${ig_unowned_view_values[2]}" <<'PY'
import json,sys
print(json.dumps({"remote_view_id":sys.argv[1],"remote_view_url":sys.argv[2],"remote_view_name":sys.argv[3]},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
  ig_state adoption-required project-view 'MVP Board' "${ig_unowned_view_values[0]}" "$ig_unowned_expected" "$ig_unowned_observed"
  printf '%s\n' 'ADOPTION REQUIRED: a Project view exists remotely but is absent from execution state.' >&2
  exit 1
fi

ig_project_is_public="$(gh project view "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --format json | uv run --locked python -c 'import json,sys; print(int(json.load(sys.stdin).get("public") is True))')"
if test "$ig_project_is_public" -eq 0; then
  ig_run_mutation '08-project-public' gh project edit "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --visibility PUBLIC --format json || exit 1
fi
ig_verify_operation '08-project-public' ig_verify_project_identity true || exit 1
ig_project_state="$(ig_state_entry project primary)"
ig_project_record="$(uv run --locked python - "$IG_PROJECT_NUMBER" "$IG_PROJECT_ID" "$IG_PROJECT_URL" "$ig_project_state" <<'PY'
import json,sys
record=json.loads(sys.argv[4]) if sys.argv[4] else {}
record.update({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"public":True,"verified":True})
record.setdefault("linked_repository",None)
print(json.dumps(record,separators=(",",":")))
PY
)"
ig_state project "$ig_project_record"

ig_link_query='query($projectId:ID!,$owner:String!,$repo:String!){node(id:$projectId){... on ProjectV2{id number title repositories(first:100){nodes{id nameWithOwner url}}}} repository(owner:$owner,name:$repo){id nameWithOwner projectsV2(first:100){nodes{id number title url}}}}'
ig_project_link_observation() {
  local payload="$1"
  uv run --locked python - "$payload" "$IG_PROJECT_ID" "$IG_PROJECT_NUMBER" "$IG_PROJECT_TITLE" "$IG_REPOSITORY_ID" "$IG_REPO" <<'PY'
import json
import sys

d=json.loads(sys.argv[1])
if d.get("errors"):
    raise SystemExit("Project link query returned GraphQL errors")
project=d.get("data",{}).get("node")
repository=d.get("data",{}).get("repository")
if not project or not repository:
    raise SystemExit("Project or repository is absent from link read-back")
if project.get("id")!=sys.argv[2] or str(project.get("number"))!=sys.argv[3] or project.get("title")!=sys.argv[4]:
    raise SystemExit("Project identity differs during link read-back")
if repository.get("id")!=sys.argv[5] or repository.get("nameWithOwner")!=sys.argv[6]:
    raise SystemExit("repository identity differs during link read-back")
project_repositories=project.get("repositories",{}).get("nodes",[])
repository_projects=repository.get("projectsV2",{}).get("nodes",[])
from_project=[row for row in project_repositories if row.get("id")==sys.argv[5] and row.get("nameWithOwner")==sys.argv[6]]
from_repository=[row for row in repository_projects if row.get("id")==sys.argv[2] and str(row.get("number"))==sys.argv[3]]
if bool(from_project)!=bool(from_repository):
    status="conflict"
elif len(from_project)==1 and len(from_repository)==1:
    status="exact"
elif not from_project and not from_repository and not project_repositories and not repository_projects:
    status="absent"
else:
    status="conflict"
properties={
    "repository_owner":sys.argv[6].split("/",1)[0],
    "repository_name":sys.argv[6].split("/",1)[1],
    "repository_name_with_owner":sys.argv[6],
    "repository_id":sys.argv[5],
    "project_number":int(sys.argv[3]),
    "project_id":sys.argv[2],
    "project_title":sys.argv[4],
}
print(json.dumps({
    "status":status,
    "properties":properties,
    "other_project_repositories":[row.get("nameWithOwner") for row in project_repositories if row.get("id")!=sys.argv[5]],
    "other_repository_projects":[{"id":row.get("id"),"number":row.get("number"),"title":row.get("title")} for row in repository_projects if row.get("id")!=sys.argv[2]],
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
}

ig_fetch_project_link() {
  gh api graphql -f query="$ig_link_query" -F projectId="$IG_PROJECT_ID" -f owner="$IG_OWNER" -f repo="$IG_REPO_NAME"
}

ig_verify_project_link() {
  local payload observation
  payload="$(ig_fetch_project_link)"
  observation="$(ig_project_link_observation "$payload")"
  uv run --locked python - "$observation" <<'PY'
import json,sys
if json.loads(sys.argv[1]).get("status")!="exact":
    raise SystemExit("repository-Project link read-back mismatch")
PY
}

ig_link_manifest_identifier="${IG_REPO}<->${IG_PROJECT_TITLE}"
ig_link_remote_identifier="${IG_PROJECT_ID}:${IG_REPOSITORY_ID}"
ig_link_expected="$(uv run --locked python - "$IG_OWNER" "$IG_REPO_NAME" "$IG_REPO" "$IG_REPOSITORY_ID" "$IG_PROJECT_NUMBER" "$IG_PROJECT_ID" "$IG_PROJECT_TITLE" <<'PY'
import json,sys
print(json.dumps({
    "repository_owner":sys.argv[1],"repository_name":sys.argv[2],
    "repository_name_with_owner":sys.argv[3],"repository_id":sys.argv[4],
    "project_number":int(sys.argv[5]),"project_id":sys.argv[6],"project_title":sys.argv[7],
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"

ig_project_state="$(ig_state_entry project primary)"
ig_link_state="$(uv run --locked python - "$ig_project_state" <<'PY'
import json,sys
record=json.loads(sys.argv[1]).get("linked_repository") if sys.argv[1] else None
if record is not None:
    print(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"

# Case A: a recorded link is reused only after its evidence and remote pair match.
if test -n "$ig_link_state"; then
  uv run --locked python - "$ig_link_state" "$ig_link_manifest_identifier" "$ig_link_remote_identifier" "$ig_link_expected" <<'PY'
import json,sys
record=json.loads(sys.argv[1]); expected=json.loads(sys.argv[4])
if record.get("resource_type")!="repository-project-link" or record.get("manifest_identifier")!=sys.argv[2] or record.get("remote_identifier")!=sys.argv[3]:
    raise SystemExit("recorded repository-Project link identity mismatch")
if record.get("expected_properties")!=expected or record.get("observed_properties")!=expected:
    raise SystemExit("recorded repository-Project link properties mismatch")
if record.get("source") not in {"created","adopted"} or record.get("verified") is not True or not record.get("verification_timestamp"):
    raise SystemExit("recorded repository-Project link is not reusable")
if record["source"]=="adopted" and (not record.get("approval_reference") or not record.get("approval_timestamp")):
    raise SystemExit("adopted repository-Project link lacks approval evidence")
PY
  ig_verify_operation '08-reuse-repository-link' ig_verify_project_link || exit 1
else
  ig_link_json="$(ig_fetch_project_link)"
  ig_link_observation="$(ig_project_link_observation "$ig_link_json")"
  ig_link_status="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$ig_link_observation")"

  # Case B: the link may be created only when absent from state and both remote directions.
  if test "$ig_link_status" = 'absent'; then
  ig_run_mutation '08-link-repository' gh project link "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --repo "$IG_REPO_NAME" || exit 1
    ig_verify_operation '08-link-repository' ig_verify_project_link || exit 1
    ig_link_record="$(uv run --locked python - "$ig_link_manifest_identifier" "$ig_link_remote_identifier" "$ig_link_expected" <<'PY'
import json,sys
from datetime import datetime,timezone
now=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
properties=json.loads(sys.argv[3])
print(json.dumps({
    "resource_type":"repository-project-link","manifest_identifier":sys.argv[1],
    "remote_identifier":sys.argv[2],"expected_properties":properties,
    "observed_properties":properties,"approval_reference":None,"approval_timestamp":None,
    "source":"created","verified":True,"verification_timestamp":now,
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
    ig_project_record="$(uv run --locked python - "$ig_project_state" "$ig_link_record" <<'PY'
import json,sys
project=json.loads(sys.argv[1]); project["linked_repository"]=json.loads(sys.argv[2])
print(json.dumps(project,ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
    ig_state project "$ig_project_record"
    ig_state verified '08-link-repository'
  # Case C: an exact but unrecorded pair is unowned and must stop for adoption.
  elif test "$ig_link_status" = 'exact'; then
    ig_link_observed="$(uv run --locked python -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1])["properties"],ensure_ascii=False,sort_keys=True,separators=(",",":")))' "$ig_link_observation")"
    ig_state adoption-required repository-project-link "$ig_link_manifest_identifier" "$ig_link_remote_identifier" "$ig_link_expected" "$ig_link_observed"
    printf 'ADOPTION REQUIRED: repository-Project link identity=%s observed=%s\n' "$ig_link_manifest_identifier" "$ig_link_observed" >&2
    printf '%s\n' 'STOP: obtain explicit approval and run only the dedicated link-adoption operation.' >&2
    exit 1
  else
    ig_state attempt '08-link-repository-conflict'
    ig_state failure '08-link-repository-conflict' 1 'conflicting repository-Project relationship; no mutation performed'
    printf 'HARD STOP: expected repository-Project pair differs from observed relationships: %s\n' "$ig_link_observation" >&2
    exit 1
  fi
fi
```

For an exact unrecorded pair, obtain this resource-specific approval: `I
approve adoption of the existing repository–Project link between
w7-mgfcode/intentguard and IntentGuard — Weekend MVP for this Gate D
execution.` Then run the separate adoption block. It rechecks both GraphQL
directions, atomically records the adoption and its approval, reads the pair
back once more, and permits section 8 to resume. It cannot replace a link to a
different repository or Project.

```bash
read -r -p 'Paste the exact repository–Project link adoption phrase: ' IG_LINK_ADOPTION_APPROVAL_REFERENCE
ig_expected_link_approval='I approve adoption of the existing repository–Project link between w7-mgfcode/intentguard and IntentGuard — Weekend MVP for this Gate D execution.'
test "$IG_LINK_ADOPTION_APPROVAL_REFERENCE" = "$ig_expected_link_approval"

ig_adoption_required="$(uv run --locked python - "$IG_STATE_FILE" "$ig_link_manifest_identifier" "$ig_link_remote_identifier" <<'PY'
import json,sys
from pathlib import Path
required=json.loads(Path(sys.argv[1]).read_text()).get("adoption_required")
if not isinstance(required,dict) or required.get("resource_type")!="repository-project-link":
    raise SystemExit("active adoption condition is not a repository-Project link")
if required.get("manifest_identifier")!=sys.argv[2] or required.get("remote_identifier")!=sys.argv[3]:
    raise SystemExit("approval does not identify the active repository-Project link")
print(json.dumps(required,ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
ig_link_json="$(ig_fetch_project_link)"
ig_link_observation="$(ig_project_link_observation "$ig_link_json")"
test "$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["status"])' "$ig_link_observation")" = 'exact'
ig_link_observed="$(uv run --locked python -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1])["properties"],ensure_ascii=False,sort_keys=True,separators=(",",":")))' "$ig_link_observation")"
test "$ig_link_observed" = "$ig_link_expected" || { printf '%s\n' 'HARD STOP: link changed after adoption was requested.' >&2; exit 1; }
ig_approval_timestamp="$(uv run --locked python -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"))')"
ig_link_adoption_record="$(uv run --locked python - "$ig_link_manifest_identifier" "$ig_link_remote_identifier" "$ig_link_expected" "$ig_link_observed" "$IG_LINK_ADOPTION_APPROVAL_REFERENCE" "$ig_approval_timestamp" <<'PY'
import json,sys
print(json.dumps({
    "resource_type":"repository-project-link","manifest_identifier":sys.argv[1],
    "remote_identifier":sys.argv[2],"expected_properties":json.loads(sys.argv[3]),
    "observed_properties":json.loads(sys.argv[4]),"approval_reference":sys.argv[5],
    "approval_timestamp":sys.argv[6],"source":"adopted","verified":True,
    "verification_timestamp":sys.argv[6],
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
ig_state adopt-project-link "$ig_link_adoption_record"
ig_verify_operation '08-adopt-repository-link' ig_verify_project_link || exit 1
printf '%s\n' 'Verified repository–Project link adoption recorded; restart section 8.'
```

## 9. Project fields and option IDs — REMOTE WRITE, Gate D

Create Priority and Estimate only when absent. An unrecorded existing custom
field requires explicit adoption. Then retrieve all fields; require exactly one
Status, Priority, Estimate, Parent issue, and Sub-issue progress field; extract
their node and required option IDs; persist all five fields; and read back exact
names and options before any item consumes the IDs.

```bash
ig_verify_priority_field() {
  gh project field-list "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --limit 100 --format json > "$IG_FIELDS_JSON_FILE"
  uv run --locked python - "$IG_FIELDS_JSON_FILE" <<'PY'
import json,sys
from pathlib import Path
rows=[row for row in json.loads(Path(sys.argv[1]).read_text())["fields"] if row.get("name")=="Priority"]
if len(rows)!=1 or [option["name"] for option in rows[0].get("options",[])] != ["MUST","SHOULD","STRETCH","POST-WEEKEND"]:
    raise SystemExit("Priority field read-back mismatch")
PY
}

ig_verify_estimate_field() {
  gh project field-list "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --limit 100 --format json > "$IG_FIELDS_JSON_FILE"
  uv run --locked python - "$IG_FIELDS_JSON_FILE" <<'PY'
import json,sys
from pathlib import Path
rows=[row for row in json.loads(Path(sys.argv[1]).read_text())["fields"] if row.get("name")=="Estimate"]
if len(rows)!=1 or not rows[0].get("id"):
    raise SystemExit("Estimate field read-back mismatch")
PY
}

gh project field-list "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --limit 100 --format json > "$IG_FIELDS_JSON_FILE"
mapfile -d '' -t ig_field_counts < <(
  uv run --locked python - "$IG_FIELDS_JSON_FILE" <<'PY'
import json,sys
from pathlib import Path
fields=json.loads(Path(sys.argv[1]).read_text())["fields"]
for name in ("Status","Priority","Estimate","Parent issue","Sub-issue progress"):
    sys.stdout.buffer.write(str(sum(row["name"]==name for row in fields)).encode()+b"\0")
PY
)
test "${ig_field_counts[0]}" -eq 1
if test "${ig_field_counts[1]}" -eq 0; then
  test -z "$(ig_state_entry fields Priority)" || exit 1
  ig_run_mutation '09-create-priority-field' gh project field-create "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --name 'Priority' --data-type SINGLE_SELECT --single-select-options 'MUST,SHOULD,STRETCH,POST-WEEKEND' --format json || exit 1
  ig_verify_operation '09-create-priority-field' ig_verify_priority_field || exit 1
elif test -z "$(ig_state_entry fields Priority)"; then
  printf '%s\n' 'STOP: unrecorded Priority field requires explicit adoption.' >&2
  exit 1
fi
if test "${ig_field_counts[2]}" -eq 0; then
  test -z "$(ig_state_entry fields Estimate)" || exit 1
  ig_run_mutation '09-create-estimate-field' gh project field-create "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --name 'Estimate' --data-type NUMBER --format json || exit 1
  ig_verify_operation '09-create-estimate-field' ig_verify_estimate_field || exit 1
elif test -z "$(ig_state_entry fields Estimate)"; then
  printf '%s\n' 'STOP: unrecorded Estimate field requires explicit adoption.' >&2
  exit 1
fi

gh project field-list "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --limit 100 --format json > "$IG_FIELDS_JSON_FILE"
mapfile -d '' -t ig_field_values < <(
  uv run --locked python - "$IG_FIELDS_JSON_FILE" "$IG_MANIFEST_FILE" <<'PY'
import json,sys
from pathlib import Path
remote=json.loads(Path(sys.argv[1]).read_text())["fields"]
manifest=json.loads(Path(sys.argv[2]).read_text())
expected={f["name"]:f for f in manifest["project"]["fields"]}
selected={}
for name in ("Status","Priority","Estimate","Parent issue","Sub-issue progress"):
    rows=[row for row in remote if row.get("name")==name]
    if len(rows)!=1 or not rows[0].get("id"):
        raise SystemExit(f"required field {name} is absent, duplicated, or has no ID")
    selected[name]=rows[0]
priority_options={row["name"]:row["id"] for row in selected["Priority"].get("options",[]) if row.get("id")}
status_options={row["name"]:row["id"] for row in selected["Status"].get("options",[]) if row.get("id")}
if list(priority_options) != expected["Priority"]["options"]:
    raise SystemExit("Priority options differ from manifest")
if list(status_options) != expected["Status"]["options"]:
    raise SystemExit("Status options differ from manifest")
values=(
    selected["Priority"]["id"], selected["Status"]["id"],
    selected["Estimate"]["id"], selected["Parent issue"]["id"],
    selected["Sub-issue progress"]["id"], priority_options.get("MUST"),
    status_options.get("Backlog"),
)
if any(not value for value in values):
    raise SystemExit("required field or option ID is empty")
for value in values:
    sys.stdout.buffer.write(value.encode()+b"\0")
PY
)
test "${#ig_field_values[@]}" -eq 7
IG_PRIORITY_FIELD_ID="${ig_field_values[0]}"
IG_STATUS_FIELD_ID="${ig_field_values[1]}"
IG_ESTIMATE_FIELD_ID="${ig_field_values[2]}"
IG_PARENT_FIELD_ID="${ig_field_values[3]}"
IG_SUB_ISSUE_PROGRESS_FIELD_ID="${ig_field_values[4]}"
IG_MUST_OPTION_ID="${ig_field_values[5]}"
IG_BACKLOG_OPTION_ID="${ig_field_values[6]}"
for ig_required_id in "$IG_PRIORITY_FIELD_ID" "$IG_STATUS_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_PARENT_FIELD_ID" "$IG_SUB_ISSUE_PROGRESS_FIELD_ID" "$IG_MUST_OPTION_ID" "$IG_BACKLOG_OPTION_ID"; do
  test -n "$ig_required_id"; test "$ig_required_id" != 'null'
done
ig_fields_record="$(uv run --locked python - "$IG_PRIORITY_FIELD_ID" "$IG_STATUS_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_PARENT_FIELD_ID" "$IG_SUB_ISSUE_PROGRESS_FIELD_ID" "$IG_MUST_OPTION_ID" "$IG_BACKLOG_OPTION_ID" <<'PY'
import json,sys
print(json.dumps({
 "Priority":{"id":sys.argv[1],"options":{"MUST":sys.argv[6]}},
 "Status":{"id":sys.argv[2],"options":{"Backlog":sys.argv[7]}},
 "Estimate":{"id":sys.argv[3],"unit":"hours"},
 "Parent issue":{"id":sys.argv[4],"type":"built-in-hierarchy"},
 "Sub-issue progress":{"id":sys.argv[5],"type":"built-in-progress"},
 "verified":True,
},separators=(",",":")))
PY
)"
ig_state fields "$ig_fields_record"
ig_state verified '09-fields-and-option-ids'
```

## 10. Legacy master/issue flow (disabled after hierarchy migration)

The pre-migration master-plus-U/C flow is retained below only as an auditable
historical reference. It is deliberately inert and must not be executed.

: <<'LEGACY_MASTER_ISSUE_FLOW'

The master is handled separately so its two-label contract and state variables
are explicit. State reuse is verified; an unrecorded title match stops for
adoption.

```text
ig_verify_issue() {
  local issue_row="$1" issue_number="$2" issue_id="$3" issue_url="$4"
  local issue_file="${IG_TEMP_DIR}/issue-readback.json"
  gh issue view "$issue_number" --repo "$IG_REPO" --json id,number,title,url,labels,body > "$issue_file"
  uv run --locked python - "$issue_row" "$issue_file" "$issue_id" "$issue_url" <<'PY'
import json,sys
from pathlib import Path
expected=json.loads(sys.argv[1]); actual=json.loads(Path(sys.argv[2]).read_text())
actual_labels=sorted(row["name"] for row in actual["labels"])
if actual["id"]!=sys.argv[3] or actual["url"]!=sys.argv[4] or actual["title"]!=expected["title"]:
    raise SystemExit("issue identity/title mismatch")
if actual_labels!=sorted(expected["resolved_labels"]):
    raise SystemExit("issue labels mismatch")
if actual["body"].rstrip("\n")!=Path(expected["body_file"]).read_text(encoding="utf-8").rstrip("\n"):
    raise SystemExit("issue body mismatch")
PY
}

mapfile -d '' -t ig_master_rows < <(ig_manifest_stream master)
test "${#ig_master_rows[@]}" -eq 1
ig_master_row="${ig_master_rows[0]}"
mapfile -d '' -t ig_master_values < <(ig_json_fields "$ig_master_row" id title body_file resolved_labels)
ig_master_key="${ig_master_values[0]}"; ig_master_title="${ig_master_values[1]}"; ig_master_body="${ig_master_values[2]}"; ig_master_labels_json="${ig_master_values[3]}"
ig_master_state="$(ig_state_entry issues "$ig_master_key")"
if test -n "$ig_master_state"; then
  mapfile -d '' -t ig_master_remote < <(ig_json_fields "$ig_master_state" number id url)
  IG_MASTER_NUMBER="${ig_master_remote[0]}"; IG_MASTER_ID="${ig_master_remote[1]}"; IG_MASTER_URL="${ig_master_remote[2]}"
  ig_verify_operation '10-reuse-master' ig_verify_issue "$ig_master_row" "$IG_MASTER_NUMBER" "$IG_MASTER_ID" "$IG_MASTER_URL" || exit 1
else
  ig_master_matches="$(gh issue list --repo "$IG_REPO" --state all --limit 1000 --json title | uv run --locked python -c 'import json,sys; print(sum(row["title"]==sys.argv[1] for row in json.load(sys.stdin)))' "$ig_master_title")"
  test "$ig_master_matches" -eq 0 || { printf '%s\n' 'STOP: unrecorded matching master requires explicit adoption.' >&2; exit 1; }
  mapfile -d '' -t ig_master_labels < <(ig_json_array_stream "$ig_master_labels_json")
  ig_master_command=(gh issue create --repo "$IG_REPO" --title "$ig_master_title" --body-file "$ig_master_body")
  for ig_master_label in "${ig_master_labels[@]}"; do ig_master_command+=(--label "$ig_master_label"); done
  ig_run_mutation '10-create-master' "${ig_master_command[@]}" || exit 1
  IG_MASTER_URL="$(tr -d '\r\n' < "$IG_MUTATION_STDOUT")"
  IG_MASTER_NUMBER="${IG_MASTER_URL##*/}"
  IG_MASTER_ID="$(gh issue view "$IG_MASTER_NUMBER" --repo "$IG_REPO" --json id --jq .id)"
  test -n "$IG_MASTER_URL"; test -n "$IG_MASTER_NUMBER"; test -n "$IG_MASTER_ID"
  ig_master_record="$(uv run --locked python - "$IG_MASTER_NUMBER" "$IG_MASTER_ID" "$IG_MASTER_URL" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"verified":False},separators=(",",":")))
PY
)"
  ig_state issue "$ig_master_key" "$ig_master_record"
  ig_verify_operation '10-create-master' ig_verify_issue "$ig_master_row" "$IG_MASTER_NUMBER" "$IG_MASTER_ID" "$IG_MASTER_URL" || exit 1
  ig_master_record="$(uv run --locked python - "$IG_MASTER_NUMBER" "$IG_MASTER_ID" "$IG_MASTER_URL" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"verified":True},separators=(",",":")))
PY
)"
  ig_state issue "$ig_master_key" "$ig_master_record"
fi
```

## 11. Umbrella and child issue loops — REMOTE WRITE, Gate D

The same safe loop is invoked first for all eight umbrellas and then for all
23 children. It reads identifier, title, body, labels, Priority, and Estimate
from each enriched manifest record, uses state before remote search, never uses
`eval`, and records each verified number, URL, and node ID atomically.

```text
ig_create_issue_row() {
  local issue_row="$1"
  local values recorded matches operation issue_url issue_number issue_id record
  local -a labels command remote_values
  mapfile -d '' -t values < <(ig_json_fields "$issue_row" id title body_file resolved_labels priority estimate_hours)
  test "${#values[@]}" -eq 6
  local issue_key="${values[0]}" issue_title="${values[1]}" body_file="${values[2]}" labels_json="${values[3]}" priority="${values[4]}" estimate="${values[5]}"
  test -f "$body_file"; test -n "$priority"; test -n "$estimate"
  operation="11-issue-${issue_key}"
  recorded="$(ig_state_entry issues "$issue_key")"
  if test -n "$recorded"; then
    mapfile -d '' -t remote_values < <(ig_json_fields "$recorded" number id url)
    test "${#remote_values[@]}" -eq 3
    ig_verify_operation "$operation" ig_verify_issue "$issue_row" "${remote_values[0]}" "${remote_values[1]}" "${remote_values[2]}" || return 1
    return 0
  fi
  matches="$(gh issue list --repo "$IG_REPO" --state all --limit 1000 --json title | uv run --locked python -c 'import json,sys; print(sum(row["title"]==sys.argv[1] for row in json.load(sys.stdin)))' "$issue_title")"
  if test "$matches" -ne 0; then
    printf 'STOP: unrecorded matching issue %s requires explicit adoption.\n' "$issue_key" >&2
    return 1
  fi
  mapfile -d '' -t labels < <(ig_json_array_stream "$labels_json")
  command=(gh issue create --repo "$IG_REPO" --title "$issue_title" --body-file "$body_file")
  for label in "${labels[@]}"; do command+=(--label "$label"); done
  ig_run_mutation "$operation" "${command[@]}" || return 1
  issue_url="$(tr -d '\r\n' < "$IG_MUTATION_STDOUT")"
  issue_number="${issue_url##*/}"
  issue_id="$(gh issue view "$issue_number" --repo "$IG_REPO" --json id --jq .id)"
  test -n "$issue_url"; test -n "$issue_number"; test -n "$issue_id"
  record="$(uv run --locked python - "$issue_number" "$issue_id" "$issue_url" "$priority" "$estimate" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"priority":sys.argv[4],"estimate_hours":float(sys.argv[5]),"verified":False},separators=(",",":")))
PY
)"
  ig_state issue "$issue_key" "$record"
  ig_verify_operation "$operation" ig_verify_issue "$issue_row" "$issue_number" "$issue_id" "$issue_url" || return 1
  record="$(uv run --locked python - "$issue_number" "$issue_id" "$issue_url" "$priority" "$estimate" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"priority":sys.argv[4],"estimate_hours":float(sys.argv[5]),"verified":True},separators=(",",":")))
PY
)"
  ig_state issue "$issue_key" "$record"
}

ig_umbrella_count=0
while IFS= read -r -d '' ig_issue_row; do
  ig_create_issue_row "$ig_issue_row" || exit 1
  ig_umbrella_count=$((ig_umbrella_count + 1))
done < <(ig_manifest_stream umbrellas)
test "$ig_umbrella_count" -eq 8

ig_child_count=0
while IFS= read -r -d '' ig_issue_row; do
  ig_create_issue_row "$ig_issue_row" || exit 1
  ig_child_count=$((ig_child_count + 1))
done < <(ig_manifest_stream children)
test "$ig_child_count" -eq 23
test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["issues"]))' "$IG_STATE_FILE")" -eq 34
```

LEGACY_MASTER_ISSUE_FLOW

## 10A. Milestone and canonical W/E/S issue flow — REMOTE WRITE, Gate D

M1 is the native top-level planning resource. `MASTER_ISSUE.md` remains its
versioned acceptance contract; no remote master issue is created. The active
flow creates M1, W01–W03, E01–E08, and S01.1–S08.3, assigns every issue to M1,
and preserves U/C values as `old_identifier` metadata.

### 10A.1 Milestone creation and verification

After duplicate absence and manifest validation, create M1 through the REST
milestones API. Record and read back its number, title, repository identity,
open state, and description source. An unrecorded exact match is an adoption
stop; it is never silently reused.

### 10A.2 Canonical issue creation

The active state-first loop is manifest-driven and creates exactly 3 umbrellas,
8 epics, and 23 subtasks. It uses canonical body paths, applies exact labels
and the M1 milestone, records issue number/node ID/URL/body checksum, and
stops for any unrecorded matching remote issue. The executable mutation blocks
are the same `ig_create_issue_row`/`ig_verify_issue` pattern as the original
runbook, with streams `umbrellas`, `epics`, and `subtasks`; no `master` stream
or issue creation exists in the active flow.

The following state-first helper is the active implementation. It performs
exact body/label/milestone read-back and records canonical/legacy identities;
an unrecorded remote match always stops for adoption.

```bash
ig_verify_issue() {
  local row="$1" number="$2" node_id="$3" url="$4" readback="${IG_TEMP_DIR}/issue-readback.json"
  gh issue view "$number" --repo "$IG_REPO" --json id,number,title,url,labels,body,milestone > "$readback"
  uv run --locked python - "$row" "$readback" "$node_id" "$url" <<'PY'
import json,sys
from pathlib import Path
expected=json.loads(sys.argv[1]); actual=json.loads(Path(sys.argv[2]).read_text())
if actual.get("id") != sys.argv[3] or actual.get("url") != sys.argv[4] or actual.get("title") != expected["title"]:
    raise SystemExit("issue identity/title mismatch")
if sorted(x["name"] for x in actual.get("labels", [])) != sorted(expected["resolved_labels"]):
    raise SystemExit("issue labels mismatch")
if actual.get("body", "").rstrip("\\n") != Path(expected["body_file"]).read_text().rstrip("\\n"):
    raise SystemExit("issue body mismatch")
milestone=actual.get("milestone") or {}
if milestone.get("title") != "IntentGuard Weekend MVP": raise SystemExit("issue milestone mismatch")
PY
}

ig_create_issue_row() {
  local row="$1"; local -a v labels cmd
  mapfile -d '' -t v < <(ig_json_fields "$row" id title body_file resolved_labels old_identifier)
  local key="${v[0]}" title="${v[1]}" body="${v[2]}" labels_json="${v[3]}" old_id="${v[4]-}"
  test -f "$body"
  local recorded="$(ig_state_entry issues "$key")"
  if test -n "$recorded"; then
    mapfile -d '' -t readback < <(ig_json_fields "$recorded" number id url)
    ig_verify_operation "10A-reuse-${key}" ig_verify_issue "$row" "${readback[0]}" "${readback[1]}" "${readback[2]}" || return 1
    return 0
  fi
  local matches="$(gh issue list --repo "$IG_REPO" --state all --limit 1000 --json title | uv run --locked python -c 'import json,sys; print(sum(x["title"]==sys.argv[1] for x in json.load(sys.stdin)))' "$title")"
  test "$matches" -eq 0 || { printf 'STOP: unrecorded matching issue %s requires explicit adoption.\n' "$key" >&2; return 1; }
  mapfile -d '' -t labels < <(ig_json_array_stream "$labels_json")
  cmd=(gh issue create --repo "$IG_REPO" --title "$title" --body-file "$body" --milestone 'IntentGuard Weekend MVP')
  for label in "${labels[@]}"; do cmd+=(--label "$label"); done
  ig_run_mutation "10A-create-${key}" "${cmd[@]}" || return 1
  local url="$(tr -d '\r\n' < "$IG_MUTATION_STDOUT")" number="${url##*/}" node_id="$(gh issue view "${url##*/}" --repo "$IG_REPO" --json id --jq .id)"
  test -n "$node_id"
  ig_state issue "$key" "$(uv run --locked python - "$number" "$node_id" "$url" "$old_id" <<'PY'
import json,sys
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"old_identifier":sys.argv[4] or None,"milestone":"M1","verified":False},separators=(",",":")))
PY
)"
  ig_verify_operation "10A-create-${key}" ig_verify_issue "$row" "$number" "$node_id" "$url" || return 1
  ig_state verified "10A-create-${key}"
}

ig_run_mutation '10A-create-milestone' gh api "repos/${IG_REPO}/milestones" --method POST \\
  -f title='IntentGuard Weekend MVP' -f description="$(cat docs/backlog/MASTER_ISSUE.md)" -f state='open' || exit 1
IG_MILESTONE_NUMBER="$(uv run --locked python -c 'import json,sys; print(json.load(sys.stdin)["number"])' < "$IG_MUTATION_STDOUT")"
test -n "$IG_MILESTONE_NUMBER"
gh api "repos/${IG_REPO}/milestones/${IG_MILESTONE_NUMBER}" > "${IG_TEMP_DIR}/milestone-readback.json"
ig_state milestone "$(printf '%s' "$IG_MILESTONE_NUMBER" | uv run --locked python -c 'import json,sys; print(json.dumps({"number":int(sys.stdin.read()),"id":"M1","source":"created","verified":True},separators=(",",":")))')"
for stream in umbrellas epics subtasks; do
  count=0
  while IFS= read -r -d '' row; do ig_create_issue_row "$row" || exit 1; count=$((count+1)); done < <(ig_manifest_stream "$stream")
  case "$stream" in umbrellas) test "$count" -eq 3;; epics) test "$count" -eq 8;; subtasks) test "$count" -eq 23;; esac
done
```

## 11. Manifest-driven hierarchy — REMOTE WRITE, Gate D

Capability detection is explicit. If `gh issue edit` documents
`--add-sub-issue`, that exact operation is used; otherwise the parameterized
GraphQL `addSubIssue` mutation is used with `replaceParent:false`. A create-only
`--parent` flag is recorded but cannot safely attach already-created issues, so
the loop uses GraphQL in that case. No parent is removed or replaced.

```bash
if gh issue edit --help | grep -q -- '--add-sub-issue'; then
  IG_CLI_SUBISSUE_MODE='edit-add-sub-issue'
elif gh issue create --help | grep -q -- '--parent'; then
  IG_CLI_SUBISSUE_MODE='create-parent-only-graphql-fallback'
else
  IG_CLI_SUBISSUE_MODE='graphql'
fi

ig_child_parent_json() {
  local child_id="$1"
  gh api graphql \
    -f query='query($childId:ID!){node(id:$childId){... on Issue{id number url parent{id number url}}}}' \
    -F childId="$child_id"
}

ig_verify_hierarchy_mutation() {
  local parent_id="$1" child_id="$2" method="$3" result_file="$4"
  if test "$method" != 'edit-add-sub-issue'; then
    uv run --locked python - "$result_file" "$parent_id" "$child_id" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
if d.get("errors"):
    raise SystemExit("addSubIssue returned GraphQL errors")
result=d.get("data",{}).get("addSubIssue")
if not result or result["issue"]["id"]!=sys.argv[2] or result["subIssue"]["id"]!=sys.argv[3] or result["subIssue"]["parent"]["id"]!=sys.argv[2]:
    raise SystemExit("addSubIssue returned a partial or mismatched result")
PY
  fi
  local parent_readback
  parent_readback="$(ig_child_parent_json "$child_id")"
  uv run --locked python - "$parent_readback" "$parent_id" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("errors") or not d.get("data",{}).get("node"):
    raise SystemExit("hierarchy read-back returned errors or a partial result")
parent=d["data"]["node"].get("parent")
if not parent or parent.get("id")!=sys.argv[2]:
    raise SystemExit("hierarchy read-back mismatch")
PY
}

ig_hierarchy_count=0
while IFS= read -r -d '' ig_relationship_row; do
  mapfile -d '' -t ig_relationship_values < <(ig_json_fields "$ig_relationship_row" key parent child)
  ig_edge_key="${ig_relationship_values[0]}"; ig_parent_key="${ig_relationship_values[1]}"; ig_child_key="${ig_relationship_values[2]}"
  ig_parent_state="$(ig_state_entry issues "$ig_parent_key")"; ig_child_state="$(ig_state_entry issues "$ig_child_key")"
  test -n "$ig_parent_state"; test -n "$ig_child_state"
  mapfile -d '' -t ig_parent_values < <(ig_json_fields "$ig_parent_state" number id url)
  mapfile -d '' -t ig_child_values < <(ig_json_fields "$ig_child_state" number id url)
  ig_parent_number="${ig_parent_values[0]}"; ig_parent_id="${ig_parent_values[1]}"; ig_child_number="${ig_child_values[0]}"; ig_child_id="${ig_child_values[1]}"
  test -n "$ig_parent_id"; test -n "$ig_child_id"
  test "$(gh issue view "$ig_parent_number" --repo "$IG_REPO" --json id --jq .id)" = "$ig_parent_id"
  test "$(gh issue view "$ig_child_number" --repo "$IG_REPO" --json id --jq .id)" = "$ig_child_id"
  ig_parent_readback="$(ig_child_parent_json "$ig_child_id")"
  ig_remote_parent="$(uv run --locked python - "$ig_parent_readback" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("errors") or not d.get("data",{}).get("node"):
    raise SystemExit("child-parent query returned errors or a partial result")
parent=d["data"]["node"].get("parent")
print("" if parent is None else parent["id"])
PY
)"
  ig_edge_state="$(ig_state_entry hierarchy "$ig_edge_key")"
  if test -n "$ig_edge_state"; then
    test "$ig_remote_parent" = "$ig_parent_id" || { printf 'STOP: recorded hierarchy mismatch %s\n' "$ig_edge_key" >&2; exit 1; }
    ig_state verified "12-hierarchy-${ig_edge_key}"
    ig_hierarchy_count=$((ig_hierarchy_count + 1))
    continue
  fi
  if test -n "$ig_remote_parent"; then
    if test "$ig_remote_parent" = "$ig_parent_id"; then
      printf 'STOP: unrecorded matching hierarchy %s requires explicit adoption.\n' "$ig_edge_key" >&2
    else
      printf 'STOP: child %s already has a conflicting parent.\n' "$ig_child_key" >&2
    fi
    exit 1
  fi
  if test "$IG_CLI_SUBISSUE_MODE" = 'edit-add-sub-issue'; then
    ig_run_mutation "12-hierarchy-${ig_edge_key}" gh issue edit "$ig_parent_number" --repo "$IG_REPO" --add-sub-issue "$ig_child_number" || exit 1
    ig_hierarchy_result="${IG_TEMP_DIR}/hierarchy-mutation.json"
    : > "$ig_hierarchy_result"
  else
    ig_run_mutation "12-hierarchy-${ig_edge_key}" gh api graphql \
      -f query='mutation($issueId:ID!,$subIssueId:ID!){addSubIssue(input:{issueId:$issueId,subIssueId:$subIssueId,replaceParent:false}){issue{id number} subIssue{id number parent{id number}}}}' \
      -F issueId="$ig_parent_id" -F subIssueId="$ig_child_id" || exit 1
    ig_hierarchy_result="${IG_TEMP_DIR}/hierarchy-mutation.json"
    cp "$IG_MUTATION_STDOUT" "$ig_hierarchy_result"
  fi
  ig_verify_operation "12-hierarchy-${ig_edge_key}" ig_verify_hierarchy_mutation "$ig_parent_id" "$ig_child_id" "$IG_CLI_SUBISSUE_MODE" "$ig_hierarchy_result" || exit 1
  ig_edge_record="$(uv run --locked python - "$ig_parent_id" "$ig_child_id" "$IG_CLI_SUBISSUE_MODE" <<'PY'
import json,sys
print(json.dumps({"parent_id":sys.argv[1],"child_id":sys.argv[2],"method":sys.argv[3],"verified":True},separators=(",",":")))
PY
)"
  ig_state hierarchy "$ig_edge_key" "$ig_edge_record"
  ig_hierarchy_count=$((ig_hierarchy_count + 1))
done < <(ig_manifest_stream relationships)
test "$ig_hierarchy_count" -eq 31
test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["hierarchy"]))' "$IG_STATE_FILE")" -eq 31
```

## 13. Manifest-driven Project items — REMOTE WRITE, Gate D

The GraphQL read-back carries both item IDs and issue URLs. Recorded items are
reverified. An existing unrecorded item requires adoption; only an absent item
is added.

```bash
ig_fetch_project_items() {
  gh api graphql \
    -f query='query($projectId:ID!){node(id:$projectId){... on ProjectV2{id items(first:100){nodes{id content{... on Issue{id number title url repository{nameWithOwner}}} fieldValues(first:50){nodes{... on ProjectV2ItemFieldSingleSelectValue{field{... on ProjectV2SingleSelectField{id name}} optionId name} ... on ProjectV2ItemFieldNumberValue{field{... on ProjectV2Field{id name}} number}}}}}}}}' \
    -F projectId="$IG_PROJECT_ID"
}

ig_verify_project_item() {
  local issue_url="$1" item_id="$2" issue_title="$3"
  ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
  uv run --locked python - "$IG_ITEMS_JSON_FILE" "$issue_url" "$item_id" "$issue_title" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
if d.get("errors"):
    raise SystemExit("Project item read-back returned errors")
rows=[row for row in d["data"]["node"]["items"]["nodes"] if row["id"]==sys.argv[3] and row.get("content",{}).get("url")==sys.argv[2] and row.get("content",{}).get("title")==sys.argv[4]]
if len(rows)!=1:
    raise SystemExit("Project item read-back mismatch")
PY
}

ig_project_item_count=0
while IFS= read -r -d '' ig_item_row; do
  mapfile -d '' -t ig_item_values < <(ig_json_fields "$ig_item_row" id title)
  ig_issue_key="${ig_item_values[0]}"; ig_issue_title="${ig_item_values[1]}"
  ig_issue_state="$(ig_state_entry issues "$ig_issue_key")"; test -n "$ig_issue_state"
  mapfile -d '' -t ig_issue_values < <(ig_json_fields "$ig_issue_state" id url)
  ig_issue_id="${ig_issue_values[0]}"; ig_issue_url="${ig_issue_values[1]}"
  ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
  mapfile -d '' -t ig_remote_item_ids < <(uv run --locked python - "$IG_ITEMS_JSON_FILE" "$ig_issue_url" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
if d.get("errors"):
    raise SystemExit("Project item query returned GraphQL errors")
for row in d["data"]["node"]["items"]["nodes"]:
    if row.get("content",{}).get("url")==sys.argv[2]:
        sys.stdout.buffer.write(row["id"].encode()+b"\0")
PY
)
  ig_item_state="$(ig_state_entry project_items "$ig_issue_key")"
  if test -n "$ig_item_state"; then
    ig_recorded_item_id="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ig_item_state")"
    test "${#ig_remote_item_ids[@]}" -eq 1; test "${ig_remote_item_ids[0]}" = "$ig_recorded_item_id"
    ig_state verified "13-project-item-${ig_issue_key}"
    ig_project_item_count=$((ig_project_item_count + 1))
    continue
  fi
  if test "${#ig_remote_item_ids[@]}" -ne 0; then
    printf 'STOP: unrecorded Project item %s requires explicit adoption.\n' "$ig_issue_key" >&2
    exit 1
  fi
  ig_run_mutation "13-project-item-${ig_issue_key}" gh project item-add "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --url "$ig_issue_url" --format json || exit 1
  ig_returned_item_id="$(uv run --locked python -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$IG_MUTATION_STDOUT")"
  test -n "$ig_returned_item_id"
  ig_verify_operation "13-project-item-${ig_issue_key}" ig_verify_project_item "$ig_issue_url" "$ig_returned_item_id" "$ig_issue_title" || exit 1
  ig_item_record="$(uv run --locked python - "$ig_returned_item_id" "$ig_issue_id" "$ig_issue_url" <<'PY'
import json,sys
print(json.dumps({"id":sys.argv[1],"issue_id":sys.argv[2],"issue_url":sys.argv[3],"values":{},"verified":True},separators=(",",":")))
PY
)"
  ig_state project-item "$ig_issue_key" "$ig_item_record"
  ig_project_item_count=$((ig_project_item_count + 1))
done < <(ig_manifest_stream project-items)
test "$ig_project_item_count" -eq 34
ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
test "$(uv run --locked python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d["data"]["node"]["items"]["nodes"]))' "$IG_ITEMS_JSON_FILE")" -eq 34
```

## 14. Manifest-driven field population — REMOTE WRITE, Gate D

Each record supplies its own Priority and Estimate. The current approved
manifest contains `MUST`, but the loop checks rather than assumes it. Missing
values are set one at a time; a non-empty conflicting value stops. Every edit
is read back before its operation is marked verified.

```bash
ig_item_field_values() {
  local item_file="$1" item_id="$2"
  uv run --locked python - "$item_file" "$item_id" "$IG_PRIORITY_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_STATUS_FIELD_ID" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
rows=[row for row in d["data"]["node"]["items"]["nodes"] if row["id"]==sys.argv[2]]
if len(rows)!=1:
    raise SystemExit("Project item ID is absent or duplicated")
found={sys.argv[3]:"",sys.argv[4]:"",sys.argv[5]:""}
for value in rows[0]["fieldValues"]["nodes"]:
    field=value.get("field") or {}
    if field.get("id") in found:
        found[field["id"]]=value.get("name",value.get("number",""))
for key in (sys.argv[3],sys.argv[4],sys.argv[5]):
    sys.stdout.buffer.write(str(found[key]).encode()+b"\0")
PY
}

ig_verify_item_field() {
  local item_id="$1" value_index="$2" expected_value="$3" value_kind="$4"
  local -a values
  ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
  mapfile -d '' -t values < <(ig_item_field_values "$IG_ITEMS_JSON_FILE" "$item_id")
  test "${#values[@]}" -eq 3
  if test "$value_kind" = 'number'; then
    uv run --locked python - "${values[$value_index]}" "$expected_value" <<'PY'
import sys
if float(sys.argv[1]) != float(sys.argv[2]):
    raise SystemExit("numeric field read-back mismatch")
PY
  else
    test "${values[$value_index]}" = "$expected_value"
  fi
}

for ig_required_id in "$IG_PROJECT_ID" "$IG_PRIORITY_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_STATUS_FIELD_ID" "$IG_MUST_OPTION_ID" "$IG_BACKLOG_OPTION_ID"; do test -n "$ig_required_id"; done
ig_populated_count=0
while IFS= read -r -d '' ig_field_row; do
  mapfile -d '' -t ig_manifest_values < <(ig_json_fields "$ig_field_row" id priority estimate_hours initial_status)
  ig_issue_key="${ig_manifest_values[0]}"; ig_priority="${ig_manifest_values[1]}"; ig_estimate="${ig_manifest_values[2]}"; ig_status="${ig_manifest_values[3]}"
  case "$ig_priority" in MUST) ig_priority_option_id="$IG_MUST_OPTION_ID" ;; *) printf 'STOP: unsupported Priority %s\n' "$ig_priority" >&2; exit 1 ;; esac
  test "$ig_status" = 'Backlog'; ig_status_option_id="$IG_BACKLOG_OPTION_ID"
  ig_item_state="$(ig_state_entry project_items "$ig_issue_key")"; test -n "$ig_item_state"
  ig_item_id="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ig_item_state")"; test -n "$ig_item_id"
  ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
  mapfile -d '' -t ig_current_values < <(ig_item_field_values "$IG_ITEMS_JSON_FILE" "$ig_item_id")
  test "${#ig_current_values[@]}" -eq 3

  if test -z "${ig_current_values[0]}"; then
    ig_run_mutation "14-priority-${ig_issue_key}" gh project item-edit --id "$ig_item_id" --project-id "$IG_PROJECT_ID" --field-id "$IG_PRIORITY_FIELD_ID" --single-select-option-id "$ig_priority_option_id" --format json || exit 1
    ig_verify_operation "14-priority-${ig_issue_key}" ig_verify_item_field "$ig_item_id" 0 "$ig_priority" text || exit 1
    ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
    mapfile -d '' -t ig_current_values < <(ig_item_field_values "$IG_ITEMS_JSON_FILE" "$ig_item_id")
  fi
  test "${ig_current_values[0]}" = "$ig_priority" || { printf 'STOP: Priority mismatch for %s\n' "$ig_issue_key" >&2; exit 1; }
  ig_state verified "14-priority-${ig_issue_key}"

  # The manifest is authoritative for every numeric Estimate assignment:
  # subtasks are direct values, while epic and umbrella values are derived
  # sums recorded as expected_rollup. GitHub is not assumed to calculate them.
  if test -n "$ig_estimate"; then
    if test -z "${ig_current_values[1]}"; then
      ig_run_mutation "14-estimate-${ig_issue_key}" gh project item-edit --id "$ig_item_id" --project-id "$IG_PROJECT_ID" --field-id "$IG_ESTIMATE_FIELD_ID" --number "$ig_estimate" --format json || exit 1
      ig_verify_operation "14-estimate-${ig_issue_key}" ig_verify_item_field "$ig_item_id" 1 "$ig_estimate" number || exit 1
      ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
      mapfile -d '' -t ig_current_values < <(ig_item_field_values "$IG_ITEMS_JSON_FILE" "$ig_item_id")
    fi
    uv run --locked python - "${ig_current_values[1]}" "$ig_estimate" <<'PY'
import sys
if float(sys.argv[1]) != float(sys.argv[2]):
    raise SystemExit("Estimate read-back mismatch")
PY
    ig_state verified "14-estimate-${ig_issue_key}"
  else
    ig_state verified "14-estimate-rollup-${ig_issue_key}"
  fi

  if test -z "${ig_current_values[2]}"; then
    ig_run_mutation "14-status-${ig_issue_key}" gh project item-edit --id "$ig_item_id" --project-id "$IG_PROJECT_ID" --field-id "$IG_STATUS_FIELD_ID" --single-select-option-id "$ig_status_option_id" --format json || exit 1
    ig_verify_operation "14-status-${ig_issue_key}" ig_verify_item_field "$ig_item_id" 2 "$ig_status" text || exit 1
    ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
    mapfile -d '' -t ig_current_values < <(ig_item_field_values "$IG_ITEMS_JSON_FILE" "$ig_item_id")
  fi
  test "${ig_current_values[2]}" = "$ig_status" || { printf 'STOP: Status mismatch for %s\n' "$ig_issue_key" >&2; exit 1; }
  ig_state verified "14-status-${ig_issue_key}"

  ig_item_record="$(uv run --locked python - "$ig_item_state" "$ig_priority" "$ig_estimate" "$ig_status" <<'PY'
import json,sys
d=json.loads(sys.argv[1]); d["values"]={"Priority":sys.argv[2],"Estimate":None if sys.argv[3]=="" else float(sys.argv[3]),"Status":sys.argv[4]}; d["verified"]=True
print(json.dumps(d,separators=(",",":")))
PY
)"
  ig_state project-item "$ig_issue_key" "$ig_item_record"
  ig_populated_count=$((ig_populated_count + 1))
done < <(ig_manifest_stream project-items)
test "$ig_populated_count" -eq 34
```

## 15. Hybrid Project views — manual Gate D boundary and UI verification

The approved views require grouping and multi-field sorting that the available
CLI/API cannot fully configure and read back. The automated Gate D phase must
therefore finish the 16 labels, 34 issues, 31 relationships, 34 Project items,
five managed fields, and all Priority/Estimate/Backlog values, record three
pending view lifecycles, and stop without calling a view-mutation API or
finalizing execution state.

### 15.1 Automated boundary — LOCAL WRITE only, then planned stop

This block verifies the automated inventory, preserves a default-view record
captured in section 8, creates pending records for the other manual views, and
exits with status 20. Status 20 is the documented manual-action boundary, not
a successful Gate D completion and not a remote-mutation failure.

```bash
uv run --locked python - "$IG_STATE_FILE" <<'PY'
import json,sys
from pathlib import Path
s=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected={"labels":16,"issues":34,"hierarchy":31,"project_items":34}
for section,count in expected.items():
    if len(s[section])!=count or any(record.get("verified") is not True for record in s[section].values()):
        raise SystemExit(f"automated Gate D inventory is incomplete: {section}")
if not s.get("project",{}).get("verified") or not s.get("fields",{}).get("verified"):
    raise SystemExit("Project or field evidence is incomplete")
for record in s["project_items"].values():
    if set(record.get("values",{}))!={"Priority","Estimate","Status"}:
        raise SystemExit("Project item field values are incomplete")
PY

# Re-read the view set before creating any manual-pending record. At this
# boundary the only permitted remote view is the state-owned default-view side
# effect captured in section 8. Any other remote view is unowned and requires
# a separate, identity-specific adoption decision.
ig_read_views_request > "$IG_VIEWS_JSON_FILE"
uv run --locked python - "$IG_STATE_FILE" "$IG_VIEWS_JSON_FILE" <<'PY'
import json,sys
from pathlib import Path
state=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
rows=payload.get("views",payload if isinstance(payload,list) else [])
if not isinstance(rows,list): raise SystemExit("Project view listing has an unsupported shape")
remote_ids={str(row.get("id") or row.get("node_id") or "") for row in rows}
if "" in remote_ids or len(remote_ids)!=len(rows): raise SystemExit("remote Project view identities are missing or duplicated")
owned_ids={
    str(record["remote_view_id"])
    for record in state["views"].values()
    if record.get("source")=="project-creation-side-effect" and record.get("remote_view_id")
}
if remote_ids!=owned_ids:
    raise SystemExit("ADOPTION REQUIRED: remote Project view set contains an unrecorded resource")
PY

while IFS= read -r -d '' ig_view_row; do
  ig_view_name="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["name"])' "$ig_view_row")"
  ig_existing_view_state="$(ig_state_entry views "$ig_view_name")"
  if test -n "$ig_existing_view_state"; then
    uv run --locked python - "$ig_existing_view_state" "$ig_view_name" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("manifest_identifier")!=sys.argv[2] or d.get("view_name")!=sys.argv[2]:
    raise SystemExit("existing view state identity mismatch")
if d.get("verified") is not True and d.get("status")!="manual-pending":
    raise SystemExit("existing view state is neither pending nor verified")
PY
    continue
  fi
  ig_pending_view_record="$(uv run --locked python - "$ig_view_row" "$IG_PROJECT_ID" "$IG_PROJECT_URL" <<'PY'
import json,sys
from datetime import datetime,timezone
view=json.loads(sys.argv[1])
directions={
    "MVP Board":["field-option-order","ascending"],
    "Full Backlog":["field-option-order","ascending","ascending"],
    "Umbrella Progress":["ascending"],
}
expected={
    "name":view["name"], "layout":view["layout"],
    "filter":"no-active-filter" if view["name"]=="Full Backlog" else view["filter"],
    "columns":view.get("columns",[]), "group_by":view.get("group_by"),
    "sort":view.get("sort",[]), "sort_directions":directions[view["name"]],
}
print(json.dumps({
    "resource_type":"project-view", "manifest_identifier":view["name"],
    "view_name":view["name"], "project_id":sys.argv[2], "project_url":sys.argv[3],
    "remote_view_id":None, "remote_view_url":None, "source":"manual-ui-required",
    "expected_properties":expected,
    "status":"manual-pending", "verified":False, "manual_required":True,
    "recorded_at":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
},ensure_ascii=False,sort_keys=True,separators=(",",":")))
PY
)"
  ig_state manual-view-pending "$ig_view_name" "$ig_pending_view_record"
done < <(ig_manifest_stream views)

test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["views"]))' "$IG_STATE_FILE")" -eq 3
printf '%s\n' \
  'MANUAL ACTION REQUIRED; Gate D remains unfinalized:' \
  '1. Rename/configure the recorded default view as MVP Board, or create MVP Board when no default was recorded.' \
  '2. Configure MVP Board exactly as specified in docs/backlog/PROJECT_CONFIGURATION.md.' \
  '3. Create and configure Full Backlog exactly as specified there.' \
  '4. Create and configure Umbrella Progress exactly as specified there; its filter must return only W01, W02, and W03.' \
  '5. Preserve exactly those three views; do not leave a fourth view.' \
  '6. Verify every required layout, filter, column, grouping, and complete sort order.' \
  '7. Record this attestation:' \
  'I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md.' \
  '8. Request authenticated read-only UI inspection; screenshots alone are insufficient.'
exit 20
```

### 15.2 User-owned manual configuration — REMOTE WRITE, Gate D

Only the user performs these UI mutations:

1. Open the recorded Project URL.
2. If section 8 recorded an implicit default view, rename and configure that
   exact view as **MVP Board**. If none was recorded, create **MVP Board**.
3. Configure **MVP Board** as a board filtered by `Priority:MUST`, grouped by
   Status, sorted first by Priority in field-option order and then by Estimate
   ascending.
4. Create **Full Backlog** as a table with no active filter, the exact columns
   Status, Priority, Parent issue, Estimate, Labels, and the sort sequence
   Priority option order, Parent issue ascending, Title ascending.
5. Create **Umbrella Progress** as a table filtered semantically by the exact
   `type:umbrella` label, with Status, Priority, Estimate, Sub-issue progress,
   sorted by Title ascending. Quoted or UI-normalized filter syntax is allowed
   only when it selects that exact label.
6. Preserve exactly these three views. Do not create a fourth view and do not
   delete or replace the recorded default view.
7. Supply this exact attestation:

   `I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md.`

The manual UI work is not completed evidence. It must be followed by a
separate authenticated, read-only UI inspection.

### 15.3 Authenticated read-only UI inspection and evidence import

The inspector must use the active `w7-mgfcode` account, open the recorded
Project and all three views, and observe the Project identity, exact view set,
names, layout, filter semantics, required visible fields or columns, grouping,
and complete sort order. Screenshots are optional supplements. They do not
replace the live UI inspection and may never be the sole basis for
`verified=true`.

The read-only inspector writes its observations to the task-specific temporary
file `$IG_UI_EVIDENCE_FILE`. The file is not execution state. Its exact shape
is:

```json
{
  "authenticated_account": "w7-mgfcode",
  "project_id": "<recorded Project node ID>",
  "project_url": "<recorded Project URL>",
  "verification_method": "authenticated-github-ui",
  "verification_timestamp": "<ISO-8601 UTC timestamp ending in Z>",
  "inspection_reference": "<non-empty UI inspection reference>",
  "attestation_reference": "I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md.",
  "screenshot_only": false,
  "views": [
    {
      "name": "<exact manifest view name>",
      "remote_view_id": "<observed unique view ID>",
      "remote_view_url": "<observed view URL>",
      "observed_properties": {},
      "checks": {},
      "screenshots": []
    }
  ]
}
```

`observed_properties` is an object, not a string. `checks` is an object with
the eleven Boolean keys generated below. Each screenshot entry, when present,
contains a non-sensitive `description` and lowercase SHA-256. The import block
validates the entire evidence document and emits three safely delimited state
records before atomically storing them through `manual-view-verified`:

```bash
test "$(gh api user --jq .login)" = "$IG_OWNER"
test -f "$IG_UI_EVIDENCE_FILE"
ig_read_views_request > "$IG_VIEWS_JSON_FILE"
mapfile -d '' -t ig_verified_view_rows < <(
  uv run --locked python - "$IG_MANIFEST_FILE" "$IG_STATE_FILE" "$IG_UI_EVIDENCE_FILE" "$IG_VIEWS_JSON_FILE" <<'PY'
import json,sys
from datetime import datetime
from pathlib import Path

manifest=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
state=json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
evidence=json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
remote_payload=json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
remote_views=remote_payload.get("views",remote_payload if isinstance(remote_payload,list) else [])
owner=manifest["repository"]["owner"]
project=state["project"]
attestation="I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md."
if evidence.get("authenticated_account")!=owner or evidence.get("verification_method")!="authenticated-github-ui":
    raise SystemExit("authenticated UI identity mismatch")
if evidence.get("project_id")!=project.get("id") or evidence.get("project_url")!=project.get("url"):
    raise SystemExit("UI evidence Project identity mismatch")
if evidence.get("attestation_reference")!=attestation or evidence.get("screenshot_only") is not False:
    raise SystemExit("UI evidence lacks exact attestation or is screenshot-only")
timestamp=evidence.get("verification_timestamp")
try:
    parsed=datetime.fromisoformat(timestamp.replace("Z","+00:00"))
except (AttributeError,ValueError) as exc:
    raise SystemExit("UI evidence timestamp is invalid") from exc
if not timestamp.endswith("Z") or parsed.tzinfo is None or not evidence.get("inspection_reference"):
    raise SystemExit("UI evidence timestamp or inspection reference is incomplete")

directions={
    "MVP Board":["field-option-order","ascending"],
    "Full Backlog":["field-option-order","ascending","ascending"],
    "Umbrella Progress":["ascending"],
}
def normalize_filter(name, value):
    if name=="Full Backlog" and value in (None,"","all real issues","no-active-filter"):
        return "no-active-filter"
    if name=="Umbrella Progress":
        compact="".join(str(value).split())
        if compact in {"label:type:umbrella",'label:"type:umbrella"',"label:'type:umbrella'"}:
            return "label:type:umbrella"
    return value

expected={}
for view in manifest["project"]["views"]:
    expected[view["name"]]={
        "name":view["name"], "layout":view["layout"],
        "filter":"no-active-filter" if view["name"]=="Full Backlog" else view["filter"],
        "columns":view.get("columns",[]), "group_by":view.get("group_by"),
        "sort":view.get("sort",[]), "sort_directions":directions[view["name"]],
    }
rows=evidence.get("views")
if not isinstance(rows,list) or len(rows)!=3 or {row.get("name") for row in rows}!=set(expected):
    raise SystemExit("UI evidence must contain exactly the three manifest views")
ids=[row.get("remote_view_id") for row in rows]; urls=[row.get("remote_view_url") for row in rows]
if any(not value for value in ids+urls) or len(set(ids))!=3 or len(set(urls))!=3:
    raise SystemExit("UI evidence view identities are missing or duplicated")
remote_ids={str(row.get("id") or row.get("node_id") or "") for row in remote_views}
remote_names={row.get("name") for row in remote_views}
if len(remote_views)!=3 or remote_ids!=set(ids) or remote_names!=set(expected):
    raise SystemExit("remote Project view set differs from authenticated UI evidence")
remote_by_id={str(row.get("id") or row.get("node_id") or ""):row for row in remote_views}
check_names={
    "authenticated_account_verified", "project_identity_verified",
    "view_identity_verified", "name_verified", "layout_verified",
    "filter_verified", "visible_fields_verified", "group_by_verified",
    "sort_verified", "exact_view_set_verified", "inspection_completed",
}
for row in rows:
    name=row["name"]; checks=row.get("checks")
    remote_row=remote_by_id[row["remote_view_id"]]
    remote_url=str(remote_row.get("html_url") or remote_row.get("url") or "")
    if not remote_url or remote_url!=row["remote_view_url"]:
        raise SystemExit(f"remote view URL differs from UI evidence: {name}")
    observed=row.get("observed_properties")
    if not isinstance(observed,dict):
        raise SystemExit(f"UI-observed view properties are not an object: {name}")
    observed={**observed,"filter":normalize_filter(name,observed.get("filter"))}
    if observed!=expected[name]:
        raise SystemExit(f"UI-observed view properties mismatch: {name}")
    if not isinstance(checks,dict) or set(checks)!=check_names or any(checks[key] is not True for key in check_names):
        raise SystemExit(f"UI checks are incomplete: {name}")
    screenshots=row.get("screenshots",[])
    if not isinstance(screenshots,list) or any(
        not isinstance(item,dict) or not item.get("description") or
        len(item.get("sha256", ""))!=64 or any(ch not in "0123456789abcdef" for ch in item["sha256"])
        for item in screenshots
    ):
        raise SystemExit(f"optional screenshot metadata is invalid: {name}")
    pending=state["views"].get(name)
    if not isinstance(pending,dict) or pending.get("status")!="manual-pending":
        raise SystemExit(f"view lacks pending lifecycle evidence: {name}")
    source="project-default-manually-configured" if pending.get("source")=="project-creation-side-effect" else "manual-ui-created"
    if pending.get("remote_view_id") and pending["remote_view_id"]!=row["remote_view_id"]:
        raise SystemExit("recorded default view identity changed")
    record={
        "resource_type":"project-view", "manifest_identifier":name,
        "view_name":name, "remote_view_id":row["remote_view_id"],
        "remote_view_url":row["remote_view_url"], "project_id":project["id"],
        "project_url":project["url"], "source":source,
        "expected_properties":expected[name], "observed_properties":observed,
        "verification_method":"authenticated-github-ui", "verified_by":owner,
        "verification_timestamp":timestamp, "attestation_reference":attestation,
        "verified":True, "manual_required":False,
        "ui_evidence":{**checks,"screenshot_only":False,"inspection_reference":evidence["inspection_reference"]},
        "screenshot_evidence":screenshots,
    }
    sys.stdout.buffer.write(json.dumps({"name":name,"record":record},ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()+b"\0")
PY
)
test "${#ig_verified_view_rows[@]}" -eq 3
for ig_verified_view_row in "${ig_verified_view_rows[@]}"; do
  mapfile -d '' -t ig_verified_view_values < <(ig_json_fields "$ig_verified_view_row" name record)
  ig_state manual-view-verified "${ig_verified_view_values[0]}" "${ig_verified_view_values[1]}"
done
ig_state verified '15-authenticated-ui-view-verification'
```

If the authenticated inspection fails, stop without changing remote views.
Record a sanitized local failure if appropriate, let the user correct the UI
manually, then rerun the complete read-only inspection. Never automatically
edit, delete, recreate, or silently adopt a view.

### 15.4 Static lifecycle scenarios — READ-ONLY

This standard-library-only simulation exercises the ten required view
lifecycle outcomes without reading GitHub or the real execution-state file:

```bash
uv run --locked python - <<'PY'
from copy import deepcopy

names={"MVP Board","Full Backlog","Umbrella Progress"}
attestation="I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md."
expected={
    "MVP Board":{"name":"MVP Board","layout":"board","filter":"Priority:MUST","columns":[],"group_by":"Status","sort":["Priority","Estimate"],"sort_directions":["field-option-order","ascending"]},
    "Full Backlog":{"name":"Full Backlog","layout":"table","filter":"no-active-filter","columns":["Status","Priority","Parent issue","Estimate","Labels"],"group_by":None,"sort":["Priority","Parent issue","Title"],"sort_directions":["field-option-order","ascending","ascending"]},
    "Umbrella Progress":{"name":"Umbrella Progress","layout":"table","filter":"label:type:umbrella","columns":["Status","Priority","Estimate","Sub-issue progress"],"group_by":None,"sort":["Title"],"sort_directions":["ascending"]},
}

def capture_default(rows):
    if len(rows)>1: raise ValueError("multiple unexpected default views")
    return None if not rows else {"manifest_identifier":"MVP Board","remote_view_id":rows[0],"source":"project-creation-side-effect","status":"manual-pending"}

def complete_record(name, remote_id):
    properties=deepcopy(expected[name])
    return {
        "manifest_identifier":name,"remote_view_id":remote_id,
        "expected_properties":deepcopy(properties),
        "observed_properties":deepcopy(properties),
        "verified":True,"manual_required":False,
        "verification_method":"authenticated-github-ui",
        "attestation_reference":attestation,
        "ui_evidence":{"inspection_completed":True,"screenshot_only":False},
    }

def finalizable(records):
    if set(records)!=names or len(records)!=3: return False
    ids=[]
    for name,record in records.items():
        ids.append(record.get("remote_view_id"))
        if record.get("manifest_identifier")!=name: return False
        if record.get("verified") is not True or record.get("manual_required") is not False: return False
        if record.get("expected_properties")!=record.get("observed_properties"): return False
        if record.get("verification_method")!="authenticated-github-ui": return False
        if record.get("attestation_reference")!=attestation: return False
        evidence=record.get("ui_evidence",{})
        if evidence.get("inspection_completed") is not True or evidence.get("screenshot_only") is not False: return False
    return all(ids) and len(set(ids))==3

results=[]
results.append(capture_default(["V1"])["manifest_identifier"]=="MVP Board")
try: capture_default(["V1","V2"])
except ValueError: results.append(True)
else: results.append(False)
valid={name:complete_record(name,f"V{index}") for index,name in enumerate(sorted(names),1)}
results.append(finalizable(valid))
results.append(not finalizable({key:value for key,value in valid.items() if key!="Full Backlog"}))
unexpected=complete_record("MVP Board","V4"); unexpected["manifest_identifier"]="Unexpected"
results.append(not finalizable({**valid,"Unexpected":unexpected}))
mismatch_results=[]
for field in ("group_by","sort","filter","layout","columns"):
    mismatch=deepcopy(valid)
    mismatch["MVP Board"]["observed_properties"][field]="wrong"
    mismatch_results.append(not finalizable(mismatch))
results.append(all(mismatch_results))
screenshot_only=deepcopy(valid); screenshot_only["MVP Board"]["ui_evidence"]={"inspection_completed":False,"screenshot_only":True}
results.append(not finalizable(screenshot_only))
manual_required=deepcopy(valid); manual_required["MVP Board"]["manual_required"]=True
results.append(not finalizable(manual_required))
missing_attestation=deepcopy(valid); missing_attestation["MVP Board"]["attestation_reference"]=""
results.append(not finalizable(missing_attestation))
before={"attempt_history":[1,2],"failure_history":[3],"adoption_history":[],"views":{}}
after=deepcopy(before); after["views"]=deepcopy(valid)
results.append(after["attempt_history"]==before["attempt_history"] and after["failure_history"]==before["failure_history"] and after["adoption_history"]==before["adoption_history"] and finalizable(after["views"]))
if results!=[True]*10: raise SystemExit(f"view lifecycle scenarios failed: {results}")
print("view_lifecycle_scenarios=10/10")
PY
```

## 16. Exact final read-only verification

Fetch current remote data without mutation. The final verifier compares
identity, visibility, settings, topics, all 16 managed labels and their
attributes, all 34 issue titles and labels, all 31 parent-child pairs, the
linked public Project, field and option IDs, all 34 items and values, and view
state against the approved manifest. Labels outside the manifest are unmanaged,
reported separately, and never added to execution state. The managed remote
subset—not the repository's complete label set—must exactly equal the 16
manifest labels.
Any extra issue or Project item fails, which also proves no optional issue was
created.

```bash
gh repo view "$IG_REPO" --json id,nameWithOwner,visibility,url,description,hasIssuesEnabled,hasProjectsEnabled,hasWikiEnabled,repositoryTopics > "${IG_TEMP_DIR}/verify-repository.json"
gh label list --repo "$IG_REPO" --limit 100 --json name,color,description > "${IG_TEMP_DIR}/verify-labels.json"
gh issue list --repo "$IG_REPO" --state all --limit 1000 --json id,number,title,url,labels > "${IG_TEMP_DIR}/verify-issues.json"
gh project view "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --format json > "${IG_TEMP_DIR}/verify-project.json"
gh project list --owner "$IG_OWNER" --limit 100 --format json > "${IG_TEMP_DIR}/verify-project-list.json"
test "$(uv run --locked python -c 'import json,sys; print(sum(row["title"]==sys.argv[2] for row in json.load(open(sys.argv[1]))["projects"]))' "${IG_TEMP_DIR}/verify-project-list.json" "$IG_PROJECT_TITLE")" -eq 1
ig_fetch_project_link > "${IG_TEMP_DIR}/verify-project-link.json"
gh project field-list "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --limit 100 --format json > "$IG_FIELDS_JSON_FILE"
ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
ig_read_views_request > "$IG_VIEWS_JSON_FILE"
: > "${IG_TEMP_DIR}/verify-relationships.jsonl"
while IFS= read -r -d '' ig_relationship_row; do
  mapfile -d '' -t ig_relationship_values < <(ig_json_fields "$ig_relationship_row" key child)
  ig_child_state="$(ig_state_entry issues "${ig_relationship_values[1]}")"
  ig_child_id="$(uv run --locked python -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$ig_child_state")"
  ig_child_parent_json "$ig_child_id" >> "${IG_TEMP_DIR}/verify-relationships.jsonl"
done < <(ig_manifest_stream relationships)

uv run --locked python - \
  "$IG_MANIFEST_FILE" "$IG_STATE_FILE" \
  "${IG_TEMP_DIR}/verify-repository.json" "${IG_TEMP_DIR}/verify-labels.json" \
  "${IG_TEMP_DIR}/verify-issues.json" "${IG_TEMP_DIR}/verify-project.json" \
  "${IG_TEMP_DIR}/verify-project-link.json" "$IG_FIELDS_JSON_FILE" \
  "$IG_ITEMS_JSON_FILE" "${IG_TEMP_DIR}/verify-relationships.jsonl" \
  "$IG_VIEWS_JSON_FILE" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

manifest=json.loads(Path(sys.argv[1]).read_text()); state=json.loads(Path(sys.argv[2]).read_text())
repo=json.loads(Path(sys.argv[3]).read_text()); labels=json.loads(Path(sys.argv[4]).read_text())
issues=json.loads(Path(sys.argv[5]).read_text()); project=json.loads(Path(sys.argv[6]).read_text())
project_link=json.loads(Path(sys.argv[7]).read_text())
fields=json.loads(Path(sys.argv[8]).read_text())["fields"]
items_payload=json.loads(Path(sys.argv[9]).read_text())
relationship_lines=[json.loads(line) for line in Path(sys.argv[10]).read_text().splitlines() if line]
views_payload=json.loads(Path(sys.argv[11]).read_text()) if Path(sys.argv[11]).stat().st_size else None

expected_repo=manifest["repository"]
topics=repo["repositoryTopics"]
if topics and isinstance(topics[0],dict): topics=[row["name"] for row in topics]
if repo["nameWithOwner"]!=f'{expected_repo["owner"]}/{expected_repo["name"]}' or repo["visibility"]!="PUBLIC": raise SystemExit("repository identity/visibility mismatch")
if repo["description"]!=expected_repo["description"] or sorted(topics)!=sorted(expected_repo["topics"]): raise SystemExit("repository description/topics mismatch")
if not repo["hasIssuesEnabled"] or not repo["hasProjectsEnabled"] or repo["hasWikiEnabled"]: raise SystemExit("repository settings mismatch")

expected_labels={row["name"]:{"name":row["name"],"color":row["color"].upper(),"description":row["description"]} for row in manifest["labels"]}
if len(expected_labels)!=16: raise SystemExit("manifest managed-label set is not exactly 16")
remote_by_name={}
for row in labels:
    remote_by_name.setdefault(row["name"],[]).append(row)
managed_remote={name for name in remote_by_name if name in expected_labels}
unrelated_remote=sorted(set(remote_by_name)-set(expected_labels))
state_label_keys=set(state["labels"])
verified_state_labels={name for name,record in state["labels"].items() if record.get("verified") is True}
if set(expected_labels)!=state_label_keys or set(expected_labels)!=verified_state_labels:
    raise SystemExit("managed label sets do not satisfy M == S == V")
for name,expected in expected_labels.items():
    rows=remote_by_name.get(name,[])
    if len(rows)!=1:
        raise SystemExit(f"managed remote label missing or duplicated: {name}")
    observed={"name":rows[0]["name"],"color":rows[0]["color"].upper(),"description":rows[0]["description"]}
    if observed!=expected:
        raise SystemExit(f"managed remote label properties differ: {name}")
    record=state["labels"][name]
    if record.get("resource_type")!="label" or record.get("manifest_identifier")!=name or record.get("remote_identifier")!=name:
        raise SystemExit(f"managed label state identity differs: {name}")
    if record.get("source") not in {"created","adopted"} or record.get("verified") is not True:
        raise SystemExit(f"managed label state source/verification differs: {name}")
    if record.get("expected_properties")!=expected or record.get("observed_properties")!=expected:
        raise SystemExit(f"managed label state properties differ: {name}")
    if record.get("color","").upper()!=expected["color"] or record.get("description")!=expected["description"]:
        raise SystemExit(f"managed label state normalized values differ: {name}")
    if record["source"]=="adopted" and (not record.get("approval_reference") or not record.get("approval_timestamp")):
        raise SystemExit(f"adopted label lacks resource-specific approval: {name}")
if managed_remote!=set(expected_labels):
    raise SystemExit("remote managed-label subset does not equal M")
print("unrelated_remote_labels="+json.dumps(unrelated_remote,ensure_ascii=False,sort_keys=True))

expected_issues={row["title"]:row for row in manifest["issues"]}
actual_issues={row["title"]:row for row in issues}
if set(actual_issues)!=set(expected_issues) or len(issues)!=34: raise SystemExit("issue title inventory mismatch")
label_names={row["name"] for row in manifest["labels"]}
for expected_title, expected in expected_issues.items():
    expected_issue_labels=expected["labels"]
    if any(name not in label_names for name in expected_issue_labels): raise SystemExit(f"unknown expected issue label: {expected_title}")
    actual_issue_labels=sorted(row["name"] for row in actual_issues[expected_title]["labels"])
    if actual_issue_labels!=sorted(expected_issue_labels): raise SystemExit(f"issue labels mismatch: {expected_title}")
if set(state["issues"])!={row["id"] for row in manifest["issues"]}: raise SystemExit("issue state keys mismatch")

if project.get("id")!=state["project"].get("id") or project.get("title")!=manifest["project"]["title"] or project.get("public") is not True: raise SystemExit("Project mismatch")
if project_link.get("errors"): raise SystemExit("Project link verification returned errors")
project_link_node=project_link.get("data",{}).get("node")
repository_link_node=project_link.get("data",{}).get("repository")
if not project_link_node or not repository_link_node: raise SystemExit("Project link read-back is incomplete")
project_side=[row for row in project_link_node.get("repositories",{}).get("nodes",[]) if row.get("id")==state["repository"].get("id") and row.get("nameWithOwner")==repo["nameWithOwner"]]
repository_side=[row for row in repository_link_node.get("projectsV2",{}).get("nodes",[]) if row.get("id")==state["project"].get("id") and str(row.get("number"))==str(state["project"].get("number"))]
if len(project_side)!=1 or len(repository_side)!=1: raise SystemExit("managed repository-Project link mismatch")
link_state=state["project"].get("linked_repository")
if not isinstance(link_state,dict): raise SystemExit("exactly one managed repository-Project link record is required")
expected_link_properties={
    "repository_owner":expected_repo["owner"],"repository_name":expected_repo["name"],
    "repository_name_with_owner":f'{expected_repo["owner"]}/{expected_repo["name"]}',
    "repository_id":state["repository"].get("id"),"project_number":state["project"].get("number"),
    "project_id":state["project"].get("id"),"project_title":manifest["project"]["title"],
}
expected_link_manifest_id=f'{expected_repo["owner"]}/{expected_repo["name"]}<->{manifest["project"]["title"]}'
expected_link_remote_id=f'{state["project"].get("id")}:{state["repository"].get("id")}'
if link_state.get("resource_type")!="repository-project-link" or link_state.get("manifest_identifier")!=expected_link_manifest_id or link_state.get("remote_identifier")!=expected_link_remote_id:
    raise SystemExit("managed repository-Project link state identity mismatch")
if link_state.get("source") not in {"created","adopted"} or link_state.get("verified") is not True:
    raise SystemExit("managed repository-Project link state is unverified")
if link_state.get("expected_properties")!=expected_link_properties or link_state.get("observed_properties")!=expected_link_properties:
    raise SystemExit("managed repository-Project link state properties mismatch")
if link_state["source"]=="adopted" and (not link_state.get("approval_reference") or not link_state.get("approval_timestamp")):
    raise SystemExit("adopted repository-Project link lacks resource-specific approval")
for name,key in (
    ("Priority","Priority"), ("Status","Status"), ("Estimate","Estimate"),
    ("Parent issue","Parent issue"),
    ("Sub-issue progress","Sub-issue progress"),
):
    remote=[row for row in fields if row.get("name")==name]
    if len(remote)!=1 or remote[0].get("id")!=state["fields"][key]["id"]: raise SystemExit(f"field mismatch: {name}")
remote_priority=next(row for row in fields if row.get("name")=="Priority")
remote_status=next(row for row in fields if row.get("name")=="Status")
priority_options={row["name"]:row["id"] for row in remote_priority.get("options",[])}
status_options={row["name"]:row["id"] for row in remote_status.get("options",[])}
if priority_options.get("MUST")!=state["fields"]["Priority"]["options"].get("MUST"): raise SystemExit("MUST option ID mismatch")
if status_options.get("Backlog")!=state["fields"]["Status"]["options"].get("Backlog"): raise SystemExit("Backlog option ID mismatch")

if items_payload.get("errors"): raise SystemExit("Project item query errors")
remote_items=items_payload["data"]["node"]["items"]["nodes"]
if len(remote_items)!=34: raise SystemExit("Project item count mismatch")
by_url={row.get("content",{}).get("url"):row for row in remote_items}
for issue in manifest["issues"]:
    saved_issue=state["issues"][issue["id"]]; saved_item=state["project_items"].get(issue["id"])
    row=by_url.get(saved_issue["url"])
    if not saved_item or not row or row["id"]!=saved_item["id"]: raise SystemExit(f"Project item mismatch: {issue['id']}")
    values={}
    for value in row["fieldValues"]["nodes"]:
        field=value.get("field") or {}; field_id=field.get("id")
        values[field_id]=value.get("name",value.get("number"))
    if values.get(state["fields"]["Priority"]["id"])!=issue["priority"]: raise SystemExit(f"Priority mismatch: {issue['id']}")
    if issue.get("estimate_hours") is not None and float(values.get(state["fields"]["Estimate"]["id"]))!=float(issue["estimate_hours"]): raise SystemExit(f"Estimate mismatch: {issue['id']}")
    if values.get(state["fields"]["Status"]["id"])!="Backlog": raise SystemExit(f"Status mismatch: {issue['id']}")

edges=[(group["parent"],child) for group in manifest["relationships"] for child in group["children"]]
if len(relationship_lines)!=31 or len(edges)!=31: raise SystemExit("relationship count mismatch")
for (parent,child),payload in zip(edges,relationship_lines,strict=True):
    if payload.get("errors"): raise SystemExit("relationship GraphQL errors")
    actual_parent=payload["data"]["node"].get("parent")
    if not actual_parent or actual_parent["id"]!=state["issues"][parent]["id"]: raise SystemExit(f"relationship mismatch: {parent}->{child}")

directions={
    "MVP Board":["field-option-order","ascending"],
    "Full Backlog":["field-option-order","ascending","ascending"],
    "Umbrella Progress":["ascending"],
}
expected_views={}
for view in manifest["project"]["views"]:
    expected_views[view["name"]]={
        "name":view["name"], "layout":view["layout"],
        "filter":"no-active-filter" if view["name"]=="Full Backlog" else view["filter"],
        "columns":view.get("columns",[]), "group_by":view.get("group_by"),
        "sort":view.get("sort",[]), "sort_directions":directions[view["name"]],
    }
if len(expected_views)!=3 or set(state["views"])!=set(expected_views):
    raise SystemExit("view state does not exactly match the three manifest views")
if views_payload is None:
    raise SystemExit("verified views lack remote read-back")
remote_views=views_payload.get("views",views_payload if isinstance(views_payload,list) else [])
if not isinstance(remote_views,list) or len(remote_views)!=3:
    raise SystemExit("remote Project must contain exactly three views")
remote_ids=[str(row.get("id") or row.get("node_id") or "") for row in remote_views]
remote_names=[row.get("name") for row in remote_views]
if any(not value for value in remote_ids) or len(set(remote_ids))!=3 or set(remote_names)!=set(expected_views):
    raise SystemExit("remote view names or IDs are missing, duplicated, or unexpected")
remote_by_id={str(row.get("id") or row.get("node_id") or ""):row for row in remote_views}
attestation="I confirm that I manually configured the three IntentGuard Project views exactly according to docs/backlog/PROJECT_CONFIGURATION.md."
required_checks={
    "authenticated_account_verified", "project_identity_verified",
    "view_identity_verified", "name_verified", "layout_verified",
    "filter_verified", "visible_fields_verified", "group_by_verified",
    "sort_verified", "exact_view_set_verified", "inspection_completed",
}
verified_ids=[]
for name,expected in expected_views.items():
    record=state["views"][name]
    mandatory={
        "resource_type","manifest_identifier","view_name","remote_view_id",
        "remote_view_url","project_id","project_url","source",
        "expected_properties","observed_properties","verification_method",
        "verified_by","verification_timestamp","attestation_reference",
        "verified","manual_required","ui_evidence","screenshot_evidence",
    }
    if mandatory-record.keys(): raise SystemExit(f"incomplete view state: {name}")
    if record["resource_type"]!="project-view" or record["manifest_identifier"]!=name or record["view_name"]!=name:
        raise SystemExit(f"view state identity mismatch: {name}")
    if record["source"] not in {"project-default-manually-configured","manual-ui-created"}:
        raise SystemExit(f"view source mismatch: {name}")
    if record["project_id"]!=state["project"]["id"] or record["project_url"]!=state["project"]["url"]:
        raise SystemExit(f"view Project identity mismatch: {name}")
    if record["expected_properties"]!=expected or record["observed_properties"]!=expected:
        raise SystemExit(f"view properties mismatch: {name}")
    if record["verification_method"]!="authenticated-github-ui" or record["verified_by"]!=manifest["repository"]["owner"]:
        raise SystemExit(f"view lacks authenticated UI verification: {name}")
    try:
        verified_at=datetime.fromisoformat(record["verification_timestamp"].replace("Z","+00:00"))
    except (AttributeError,ValueError) as exc:
        raise SystemExit(f"view verification timestamp is invalid: {name}") from exc
    if not record["verification_timestamp"].endswith("Z") or verified_at.tzinfo is None:
        raise SystemExit(f"view verification timestamp is not UTC: {name}")
    if record["attestation_reference"]!=attestation or record["verified"] is not True or record["manual_required"] is not False:
        raise SystemExit(f"view attestation or completion state mismatch: {name}")
    evidence=record["ui_evidence"]
    if not isinstance(evidence,dict) or required_checks-evidence.keys() or any(evidence[key] is not True for key in required_checks):
        raise SystemExit(f"view UI evidence is incomplete: {name}")
    if evidence.get("screenshot_only") is not False or not evidence.get("inspection_reference"):
        raise SystemExit(f"screenshot-only view evidence is forbidden: {name}")
    screenshots=record["screenshot_evidence"]
    if not isinstance(screenshots,list): raise SystemExit(f"invalid screenshot metadata: {name}")
    if remote_ids.count(record["remote_view_id"])!=1 or remote_names.count(name)!=1:
        raise SystemExit(f"remote view identity mismatch: {name}")
    remote_row=remote_by_id[record["remote_view_id"]]
    remote_url=str(remote_row.get("html_url") or remote_row.get("url") or "")
    if not remote_url or remote_url!=record["remote_view_url"]:
        raise SystemExit(f"remote view URL mismatch: {name}")
    verified_ids.append(record["remote_view_id"])
if len(set(verified_ids))!=3 or set(verified_ids)!=set(remote_ids):
    raise SystemExit("manifest/state/remote verified-view sets differ")

expected_state_counts={"labels":16,"issues":34,"hierarchy":31,"project_items":34,"views":3}
for section,count in expected_state_counts.items():
    if len(state[section])!=count: raise SystemExit(f"state count mismatch: {section}")
if set(state["hierarchy"])!={f"{p}->{c}" for p,c in edges}: raise SystemExit("hierarchy state keys mismatch")
print("verified repository=1 labels=16 issues=34 hierarchy=31 project_items=34 views=3")
PY
ig_state verified 'final-read-only-verification'
```

## 17. Final state, timestamp, and checksum — LOCAL WRITE

The checksum is intentionally non-self-referential: set `state_sha256` to the
empty string, serialize the complete state as UTF-8 JSON with sorted keys,
`ensure_ascii=false`, and separators `(',', ':')`, then hash those bytes with
SHA-256. The helper stores that digest atomically.

```bash
test "$(uv run --locked python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(int(d["failed_operation"] is None and d["error"] is None))' "$IG_STATE_FILE")" -eq 1
test "$(ig_sha256 "$IG_MANIFEST_FILE")" = "$(uv run --locked python -c 'import json,sys; print(json.load(open(sys.argv[1]))["manifest_sha256"])' "$IG_STATE_FILE")"
ig_finalized_at="$(uv run --locked python -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"))')"
ig_state finalize "$ig_finalized_at"

uv run --locked python - "$IG_STATE_FILE" "$IG_MANIFEST_FILE" <<'PY'
import hashlib,json,sys
from pathlib import Path
state_path=Path(sys.argv[1]); manifest_path=Path(sys.argv[2])
state=json.loads(state_path.read_text(encoding="utf-8"))
stored=state["state_sha256"]
state["state_sha256"]=""
canonical=json.dumps(state,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
actual=hashlib.sha256(canonical).hexdigest()
if stored!=actual: raise SystemExit("execution-state checksum mismatch")
if state["manifest_sha256"]!=hashlib.sha256(manifest_path.read_bytes()).hexdigest(): raise SystemExit("manifest checksum mismatch")
if not state["completed"] or state["failed_operation"] is not None: raise SystemExit("execution state is not complete")
json.loads(state_path.read_text(encoding="utf-8"))
print(f'completed repository={state["repository"].get("id") is not None} project={state["project"].get("number")} labels={len(state["labels"])} issues={len(state["issues"])} hierarchy={len(state["hierarchy"])} items={len(state["project_items"])} views={len(state["views"])}')
PY
```

Finalization stops if any collection is incomplete, any managed record is
unverified, any view is pending or `manual_required=true`, authenticated UI
evidence or the exact attestation is missing, the three view names or remote
IDs are not unique, expected and observed view properties differ, a failure
remains current, or the manifest checksum changed. Screenshot evidence alone
never satisfies the view gate.

## 18. Partial failure and exact resume protocol

On failure, do not issue another mutation. The wrapper has already recorded
the failed operation, sanitized error, exit code, and retained history. Validate
state and the immutable manifest before resuming:

```bash
uv run --locked python - "$IG_STATE_FILE" "$IG_MANIFEST_FILE" <<'PY'
import hashlib,json,sys
from pathlib import Path
state_path=Path(sys.argv[1]); manifest_path=Path(sys.argv[2])
state=json.loads(state_path.read_text(encoding="utf-8"))
if state.get("schema_version")!=1: raise SystemExit("unsupported state schema")
if state.get("manifest_path")!=str(manifest_path): raise SystemExit("manifest path mismatch")
if state.get("manifest_sha256")!=hashlib.sha256(manifest_path.read_bytes()).hexdigest(): raise SystemExit("manifest changed; do not resume")
for section in ("repository","project","labels","issues","hierarchy","project_items","fields","views"):
    if not isinstance(state.get(section),dict): raise SystemExit(f"invalid state section: {section}")
if state.get("adoption_required") is not None and not isinstance(state["adoption_required"],dict):
    raise SystemExit("invalid adoption-required condition")
if not isinstance(state.get("adoption_history"),list) or not isinstance(state.get("failure_history"),list):
    raise SystemExit("invalid audit history")
print(f'last_attempted={state["last_attempted_operation"]} last_verified={state["last_verified_operation"]} failed={state["failed_operation"]}')
PY
ig_manifest_stream validate
```

For a normal mutation failure, rerun sections 1–16 in order after resolving the
external cause. Each loop verifies every recorded resource against GitHub
before reuse, stops at the first mismatch, and creates only the first absent
approved resource.

For an adoption stop, resume in this exact order:

1. Parse and validate the state with the block above.
2. Recalculate the immutable manifest hash and stop if it changed.
3. Read `adoption_required` and confirm the user's approval names that exact
   resource; a generic or multi-resource approval is invalid.
4. Run only the dedicated label or repository–Project adoption block.
5. Query the resource again and require exact expected/observed identity and
   properties.
6. Let `ig_state adopt-label` or `ig_state adopt-project-link` atomically write
   the verified record and append it to `adoption_history`.
7. Confirm the helper cleared `adoption_required`; it must not clear
   `failure_history`.
8. Record `last_verified_operation` only through the post-adoption read-back.
9. Restart the original label loop or section 8.
10. Reverify every earlier state-owned resource before the next mutation.

For the manual-view boundary or a failed UI inspection, resume additively in
this exact order:

1. Parse execution state and require schema version 1.
2. Recalculate the immutable manifest and execution-state checksums; stop on
   either mismatch.
3. Read back every previously recorded label, Project identity/link, field,
   issue, hierarchy relationship, Project item, and populated value.
4. Require exactly three pending or verified view keys matching the manifest.
5. If any remote view identity or configuration differs, stop. The user—not
   automation—must correct the GitHub UI under current Gate D approval.
6. Repeat the complete authenticated, read-only UI inspection from section
   15.3. Screenshots alone are not a retry mechanism.
7. Atomically replace only pending view records whose live UI inspection fully
   passes with `manual-view-verified`; preserve all attempt, failure, adoption,
   repository, and earlier Gate D evidence.
8. Run the complete manifest/state/remote read-back from section 16.
9. Finalize only after all three view records are verified, not manual-required,
   uniquely identified, and exact-property matches.

Never automatically edit, delete, recreate, or replace a view during recovery.
An unrecorded remote view still requires explicit resource-specific adoption;
manual creation approval does not silently adopt a pre-existing resource.

Never recreate a verified resource, use force as normal recovery, delete a
resource, change credentials silently, or adopt an unrecorded match without
resource-specific approval. The `failure_history` and `adoption_history`
arrays are append-only, so earlier errors and approvals remain auditable after
a successful read-back clears only the current `failed_operation` and `error`.

## Ordered gate checklist

| Section | Operation | Class | Gate |
|---:|---|---|---|
| 1–2 | Prerequisites, scopes, variables, manifest validation | READ-ONLY | C/D preflight |
| 3–5 | State initialization and atomic helpers | LOCAL WRITE | C/D evidence |
| 6 | Repository creation, separate push, metadata/topics | LOCAL + REMOTE WRITE | C |
| 8 | Create/link Project and capture its default-view side effect | REMOTE WRITE | D |
| 7 | Reconcile and record 16 labels | REMOTE WRITE | D |
| 9 | Create/extract all five Project fields and required options | REMOTE WRITE | D |
| 10A | Create/record M1, 3 umbrellas, 8 epics, 23 subtasks | REMOTE WRITE | D |
| 12 | Apply and verify 31 hierarchy relationships | REMOTE WRITE | D |
| 13–14 | Add 34 Project items and populate three fields | REMOTE WRITE | D |
| 15.1 | Record three pending view lifecycles and stop automation | LOCAL WRITE | D evidence |
| 15.2 | User configures exactly three views in GitHub UI | USER MANUAL REMOTE WRITE | D |
| 15.3 | Authenticated UI inspection and verified view-state import | READ-ONLY REMOTE + LOCAL WRITE | D evidence |
| 16 | Compare all managed remote resources with the manifest | READ-ONLY | D completion |
| 17–18 | Finalize checksummed state or resume additively | LOCAL WRITE / READ-ONLY | Evidence |

No command in this document authorizes its own execution. Gate approval must
be current and explicit immediately before the corresponding remote mutation.
