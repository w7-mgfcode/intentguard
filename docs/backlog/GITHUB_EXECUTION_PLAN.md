# Ordered GitHub execution plan

This is an inert, command-complete runbook for approved Gates C and D. The
commands in this document are examples for a future approved execution; they
must not be run while preparing or validating this documentation. Gate C
authorizes repository creation, remote configuration, and the reviewed push.
Gate D separately authorizes labels, the Project, fields, issues, hierarchy,
items, field values, and views. Resource adoption is never implicit: an exact
remote match that is absent from execution state is unowned until a separate,
identity-specific approval and adoption operation succeeds.

Run every block below from the reviewed repository root in **one Bash
session**, in order. Never print credentials, silently switch accounts, use
`--force`, delete and recreate a resource as recovery, or use
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

if len(labels) != 15 or len(label_names) != 15:
    raise SystemExit("manifest must contain 15 unique labels")
counts = Counter(row.get("type") for row in issues)
if counts != {"master": 1, "umbrella": 8, "task": 23} or len(issues) != 32:
    raise SystemExit(f"invalid issue inventory: {dict(counts)}")
ids = [row["id"] for row in issues]
orders = [row["creation_order"] for row in issues]
if len(set(ids)) != 32 or len(set(orders)) != 32 or orders != list(range(1, 33)):
    raise SystemExit("issue IDs or creation_order values are not unique and contiguous")
by_id = {row["id"]: row for row in issues}
if issues[0]["type"] != "master" or issues[0]["parent"] is not None:
    raise SystemExit("the first issue must be the parentless master")

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
        raise SystemExit(f"invalid estimate for {row['id']}")
    if not Path(row["body_file"]).is_file():
        raise SystemExit(f"missing body file for {row['id']}")
    if row["type"] == "master":
        resolved_labels = row.get("labels", [])
    else:
        resolved_labels = [f"type:{row['type']}", f"priority:{row['priority']}", f"area:{row['area']}"]
    if not resolved_labels or any(name not in label_names for name in resolved_labels):
        raise SystemExit(f"unknown resolved label for {row['id']}")
    enriched.append({**row, "resolved_labels": resolved_labels, "initial_status": "Backlog"})

edges = []
for group_index, group in enumerate(m["relationships"]):
    parent = group["parent"]
    if parent not in by_id:
        raise SystemExit(f"unknown relationship parent: {parent}")
    for child_index, child in enumerate(group["children"]):
        if child not in by_id or by_id[child]["parent"] != parent:
            raise SystemExit(f"invalid relationship: {parent}->{child}")
        edges.append({
            "key": f"{parent}->{child}",
            "parent": parent,
            "child": child,
            "creation_order": [group_index, child_index],
        })
if len(edges) != 31 or len({edge["child"] for edge in edges}) != 31:
    raise SystemExit("manifest must contain 31 unique child relationships")

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
    "master": [row for row in enriched if row["type"] == "master"],
    "umbrellas": [row for row in enriched if row["type"] == "umbrella"],
    "children": [row for row in enriched if row["type"] == "task"],
    "relationships": edges,
    "project-items": enriched,
    "priorities": [{"id": row["id"], "priority": row["priority"]} for row in enriched],
    "estimates": [{"id": row["id"], "estimate_hours": row["estimate_hours"]} for row in enriched],
    "statuses": [{"id": row["id"], "status": "Backlog"} for row in enriched],
    "views": m["project"]["views"],
}
if stream == "validate":
    print(json.dumps({
        "master": counts["master"], "umbrellas": counts["umbrella"],
        "children": counts["task"], "issues": len(issues),
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
for ig_stream in labels master umbrellas children relationships project-items priorities estimates statuses views; do
  ig_stream_count=0
  while IFS= read -r -d '' ig_record; do
    ig_stream_count=$((ig_stream_count + 1))
  done < <(ig_manifest_stream "$ig_stream")
  printf '%s=%s\n' "$ig_stream" "$ig_stream_count"
done
```

Expected counts are `15, 1, 8, 23, 31, 32, 32, 32, 32, 3` in the
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
    "manifest_path": str(manifest),
    "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    "repository": {},
    "project": {},
    "labels": {},
    "issues": {},
    "hierarchy": {},
    "project_items": {},
    "fields": {},
    "views": {},
    "adoption_required": None,
    "adoption_history": [],
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

if operation == "set-scalar":
    require(2)
    field, raw = args
    protected = {"schema_version", "manifest_path", "manifest_sha256", "last_verified_operation", "failed_operation", "error", "completed", "finalized_at", "state_sha256"}
    if field not in state or field in protected or isinstance(state[field], (dict, list)):
        raise SystemExit("invalid scalar field")
    state[field] = json.loads(raw)
elif operation in {"repository", "project", "fields"}:
    require(1)
    state[operation] = object_arg(args[0])
elif operation in {"label", "issue", "hierarchy", "project-item", "view"}:
    require(2)
    key, raw = args
    section = {"label": "labels", "issue": "issues", "hierarchy": "hierarchy", "project-item": "project_items", "view": "views"}[operation]
    if not key:
        raise SystemExit("state record key is empty")
    state[section][key] = object_arg(raw)
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
    expected = {"labels": 15, "issues": 32, "hierarchy": 31, "project_items": 32, "views": 3}
    for section, count in expected.items():
        if len(state[section]) != count:
            raise SystemExit(f"incomplete {section}: {len(state[section])}/{count}")
    if state["failed_operation"] is not None or state["error"] is not None:
        raise SystemExit("cannot finalize with a current failure")
    if state.get("adoption_required") is not None:
        raise SystemExit("cannot finalize while adoption is required")
    if state.get("last_verified_operation") != "final-read-only-verification":
        raise SystemExit("final remote read-back has not been verified")
    if not state["repository"].get("verified") or not state["project"].get("verified"):
        raise SystemExit("repository or Project is not verified")
    if not state["fields"].get("verified"):
        raise SystemExit("Project fields are not verified")
    for section in ("labels", "issues", "hierarchy", "project_items"):
        if any(not record.get("verified") for record in state[section].values()):
            raise SystemExit(f"unverified record in {section}")
    manifest_labels = {row["name"] for row in manifest["labels"]}
    if len(manifest_labels) != 15 or set(state["labels"]) != manifest_labels:
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
    for record in state["views"].values():
        if not (record.get("verified") is True or record.get("manual_required") is True):
            raise SystemExit("view lacks verification or manual-required status")
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

The loop processes the 15 manifest labels in array order and always consults
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
test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["labels"]))' "$IG_STATE_FILE")" -eq 15
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
The creation result and public visibility are immediately read back.

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
print(json.dumps({"number":int(sys.argv[1]),"id":sys.argv[2],"url":sys.argv[3],"public":False,"linked_repository":None,"verified":True},separators=(",",":")))
PY
)"
  ig_state project "$ig_project_record"
fi
test -n "$IG_PROJECT_NUMBER"; test -n "$IG_PROJECT_ID"; test -n "$IG_PROJECT_URL"

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
field requires explicit adoption. Then retrieve all fields, require exactly one
Status, Priority, and Estimate, extract node/option IDs, persist them, and read
back exact names and options before any item consumes the IDs.

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
for name in ("Status","Priority","Estimate"):
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
for name in ("Status","Priority","Estimate"):
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
values=(selected["Priority"]["id"],selected["Status"]["id"],selected["Estimate"]["id"],priority_options.get("MUST"),status_options.get("Backlog"))
if any(not value for value in values):
    raise SystemExit("required field or option ID is empty")
for value in values:
    sys.stdout.buffer.write(value.encode()+b"\0")
PY
)
test "${#ig_field_values[@]}" -eq 5
IG_PRIORITY_FIELD_ID="${ig_field_values[0]}"
IG_STATUS_FIELD_ID="${ig_field_values[1]}"
IG_ESTIMATE_FIELD_ID="${ig_field_values[2]}"
IG_MUST_OPTION_ID="${ig_field_values[3]}"
IG_BACKLOG_OPTION_ID="${ig_field_values[4]}"
for ig_required_id in "$IG_PRIORITY_FIELD_ID" "$IG_STATUS_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_MUST_OPTION_ID" "$IG_BACKLOG_OPTION_ID"; do
  test -n "$ig_required_id"; test "$ig_required_id" != 'null'
done
ig_fields_record="$(uv run --locked python - "$IG_PRIORITY_FIELD_ID" "$IG_STATUS_FIELD_ID" "$IG_ESTIMATE_FIELD_ID" "$IG_MUST_OPTION_ID" "$IG_BACKLOG_OPTION_ID" <<'PY'
import json,sys
print(json.dumps({
 "Priority":{"id":sys.argv[1],"options":{"MUST":sys.argv[4]}},
 "Status":{"id":sys.argv[2],"options":{"Backlog":sys.argv[5]}},
 "Estimate":{"id":sys.argv[3],"unit":"hours"},"verified":True,
},separators=(",",":")))
PY
)"
ig_state fields "$ig_fields_record"
ig_state verified '09-fields-and-option-ids'
```

## 10. Master issue — REMOTE WRITE, Gate D

The master is handled separately so its two-label contract and state variables
are explicit. State reuse is verified; an unrecorded title match stops for
adoption.

```bash
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

```bash
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
test "$(uv run --locked python -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["issues"]))' "$IG_STATE_FILE")" -eq 32
```

## 12. Manifest-driven hierarchy — REMOTE WRITE, Gate D

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
test "$ig_project_item_count" -eq 32
ig_fetch_project_items > "$IG_ITEMS_JSON_FILE"
test "$(uv run --locked python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d["data"]["node"]["items"]["nodes"]))' "$IG_ITEMS_JSON_FILE")" -eq 32
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
d=json.loads(sys.argv[1]); d["values"]={"Priority":sys.argv[2],"Estimate":float(sys.argv[3]),"Status":sys.argv[4]}; d["verified"]=True
print(json.dumps(d,separators=(",",":")))
PY
)"
  ig_state project-item "$ig_issue_key" "$ig_item_record"
  ig_populated_count=$((ig_populated_count + 1))
done < <(ig_manifest_stream project-items)
test "$ig_populated_count" -eq 32
```

## 15. Project views — REMOTE WRITE or explicit manual Gate D stop

GitHub's documented REST create-view operation accepts `name`, `layout`,
`filter`, and optional visible field REST IDs. It does not currently express
all approved grouping and multi-field sorting settings. Consequently, the
automated path must stop before creating partial views unless a capability
probe proves every manifest property can be applied and read back.

Exact supported request templates are:

```bash
if test "$IG_OWNER_TYPE" = 'Organization'; then
  ig_views_endpoint="orgs/${IG_OWNER}/projectsV2/${IG_PROJECT_NUMBER}/views"
else
  ig_views_endpoint="users/${IG_OWNER_ID}/projectsV2/${IG_PROJECT_NUMBER}/views"
fi

# Supported create template; run only after a successful full-capability probe.
ig_create_view_request() {
  local view_name="$1" view_layout="$2" view_filter="$3"
  gh api --method POST -H "X-GitHub-Api-Version: ${IG_API_VERSION}" "$ig_views_endpoint" \
    -f name="$view_name" -f layout="$view_layout" -f filter="$view_filter"
}

# Supported list/read-back template.
ig_read_views_request() {
  gh api -H "X-GitHub-Api-Version: ${IG_API_VERSION}" "$ig_views_endpoint"
}

ig_record_manual_view() {
  local view_name="$1" view_layout="$2" view_filter="$3" api_result="$4" error_classification="$5"
  local view_record
  view_record="$(uv run --locked python - "$view_name" "$view_layout" "$view_filter" "$api_result" "$error_classification" <<'PY'
import json,sys
print(json.dumps({
 "requested_name":sys.argv[1],"requested_layout":sys.argv[2],"requested_filter":sys.argv[3],
 "api_result":sys.argv[4],"id":None,"verified":False,"manual_required":True,
 "error_classification":sys.argv[5],
},separators=(",",":")))
PY
)"
  ig_state view "$view_name" "$view_record"
}

# Call only when a capability probe has proved every requested property can be
# applied. A failed request is recorded and stops; a 401/403 is never retried.
ig_verify_supported_view_result() {
  local result_file="$1" view_name="$2" view_layout="$3" view_filter="$4" verified_file="$5"
  ig_read_views_request > "$IG_VIEWS_JSON_FILE"
  uv run --locked python - "$result_file" "$IG_VIEWS_JSON_FILE" "$view_name" "$view_layout" "$view_filter" "$verified_file" <<'PY'
import json,sys
from pathlib import Path
created=json.loads(Path(sys.argv[1]).read_text()); listing=json.loads(Path(sys.argv[2]).read_text())
views=listing.get("views",listing if isinstance(listing,list) else [])
record={"id":created.get("id"),"node_id":created.get("node_id"),"number":created.get("number"),"url":created.get("html_url")}
if not all(value is not None for value in record.values()): raise SystemExit("view creation returned incomplete identifiers")
matches=[row for row in views if str(row.get("id"))==str(record["id"]) and row.get("name")==sys.argv[3] and row.get("layout")==sys.argv[4] and (row.get("filter") or "")==sys.argv[5]]
if len(matches)!=1: raise SystemExit("view read-back mismatch")
Path(sys.argv[6]).write_text(json.dumps(record,separators=(",",":")),encoding="utf-8")
PY
}

ig_create_and_verify_supported_view() {
  local view_name="$1" view_layout="$2" view_filter="$3"
  local operation="15-view-${view_name}" result_file="${IG_TEMP_DIR}/view-create-result.json" verified_file="${IG_TEMP_DIR}/view-verified.json"
  local -a view_ids
  if ! ig_run_mutation "$operation" ig_create_view_request "$view_name" "$view_layout" "$view_filter"; then
    ig_record_manual_view "$view_name" "$view_layout" "$view_filter" 'failed' 'api_auth_or_capability_failure'
    return 1
  fi
  cp "$IG_MUTATION_STDOUT" "$result_file"
  if ! ig_verify_operation "$operation" ig_verify_supported_view_result "$result_file" "$view_name" "$view_layout" "$view_filter" "$verified_file"; then
    ig_record_manual_view "$view_name" "$view_layout" "$view_filter" 'created_but_unverified' 'readback_or_configuration_failure'
    return 1
  fi
  mapfile -d '' -t view_ids < <(uv run --locked python - "$verified_file" <<'PY'
import json,sys
from pathlib import Path
d=json.loads(Path(sys.argv[1]).read_text())
for key in ("id","node_id","number","url"): sys.stdout.buffer.write(str(d[key]).encode()+b"\0")
PY
)
  test "${#view_ids[@]}" -eq 4
  local view_record
  view_record="$(uv run --locked python - "$view_name" "$view_layout" "$view_filter" "${view_ids[0]}" "${view_ids[1]}" "${view_ids[2]}" "${view_ids[3]}" <<'PY'
import json,sys
print(json.dumps({"requested_name":sys.argv[1],"requested_layout":sys.argv[2],"requested_filter":sys.argv[3],"api_result":"created","id":sys.argv[4],"node_id":sys.argv[5],"number":int(sys.argv[6]),"url":sys.argv[7],"verified":True,"manual_required":False,"error_classification":None},separators=(",",":")))
PY
)"
  ig_state view "$view_name" "$view_record"
}
```

For the currently approved manifest, record the unsupported configuration and
stop automated view mutation without invoking `ig_create_view_request`:

```bash
while IFS= read -r -d '' ig_view_row; do
  mapfile -d '' -t ig_view_values < <(ig_json_fields "$ig_view_row" name layout filter)
  ig_view_name="${ig_view_values[0]}"; ig_view_layout="${ig_view_values[1]}"; ig_view_filter="${ig_view_values[2]}"
  ig_record_manual_view "$ig_view_name" "$ig_view_layout" "$ig_view_filter" 'not_attempted' 'unsupported_configuration'
done < <(ig_manifest_stream views)
ig_state verified '15-views-manual-boundary-recorded'
```

If a future capability probe demonstrates full support, call
`ig_run_mutation` with `ig_create_view_request`, parse the returned `id`,
`number`, `node_id`, and `html_url`, call `ig_read_views_request`, require one
exact read-back, and store those identifiers with `verified=true` and
`manual_required=false`. On 401, 403, or an unsupported property, record
`api_result`, `id=null` when none was returned, `verified=false`,
`manual_required=true`, and an error classification, then stop automated view
configuration while preserving verified resources.

Manual Gate D steps are exact:

1. Run `gh project view "$IG_PROJECT_NUMBER" --owner "$IG_OWNER" --web`.
2. Configure **MVP Board** as board, filter `Priority:MUST`, group by Status,
   sort by Priority then Estimate.
3. Configure **Full Backlog** as table showing Status, Priority, Parent issue,
   Estimate, Labels; sort by Priority, Parent issue, Title.
4. Configure **Umbrella Progress** as table filtered by
   `label:type:umbrella`, showing Status, Priority, Estimate, Sub-issue
   progress; sort by Title.
5. Save and read back exactly three views. Update each state record only after
   its complete configuration is verified; a manual instruction is never
   automatically marked complete.

## 16. Exact final read-only verification

Fetch current remote data without mutation. The final verifier compares
identity, visibility, settings, topics, all 15 managed labels and their
attributes, all 32 issue titles and labels, all 31 child-parent pairs, the
linked public Project, field and option IDs, all 32 items and values, and view
state against the approved manifest. Labels outside the manifest are unmanaged,
reported separately, and never added to execution state. The managed remote
subset—not the repository's complete label set—must exactly equal the 15
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
ig_read_views_request > "$IG_VIEWS_JSON_FILE" || true
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
if len(expected_labels)!=15: raise SystemExit("manifest managed-label set is not exactly 15")
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
if set(actual_issues)!=set(expected_issues) or len(issues)!=32: raise SystemExit("issue title inventory mismatch")
label_names={row["name"] for row in manifest["labels"]}
for expected_title, expected in expected_issues.items():
    if expected["type"]=="master": expected_issue_labels=expected["labels"]
    else: expected_issue_labels=[f'type:{expected["type"]}',f'priority:{expected["priority"]}',f'area:{expected["area"]}']
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
for name,key in (("Priority","Priority"),("Status","Status"),("Estimate","Estimate")):
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
if len(remote_items)!=32: raise SystemExit("Project item count mismatch")
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
    if float(values.get(state["fields"]["Estimate"]["id"]))!=float(issue["estimate_hours"]): raise SystemExit(f"Estimate mismatch: {issue['id']}")
    if values.get(state["fields"]["Status"]["id"])!="Backlog": raise SystemExit(f"Status mismatch: {issue['id']}")

edges=[(group["parent"],child) for group in manifest["relationships"] for child in group["children"]]
if len(relationship_lines)!=31 or len(edges)!=31: raise SystemExit("relationship count mismatch")
for (parent,child),payload in zip(edges,relationship_lines,strict=True):
    if payload.get("errors"): raise SystemExit("relationship GraphQL errors")
    actual_parent=payload["data"]["node"].get("parent")
    if not actual_parent or actual_parent["id"]!=state["issues"][parent]["id"]: raise SystemExit(f"relationship mismatch: {parent}->{child}")

if len(state["views"])!=3: raise SystemExit("view state count mismatch")
for view in manifest["project"]["views"]:
    record=state["views"].get(view["name"])
    if not record or not (record.get("verified") is True or record.get("manual_required") is True): raise SystemExit(f"view status incomplete: {view['name']}")
    if record.get("verified"):
        if views_payload is None: raise SystemExit("verified views lack remote read-back")
        remote_views=views_payload.get("views",views_payload if isinstance(views_payload,list) else [])
        matches=[row for row in remote_views if row.get("name")==view["name"] and str(row.get("id"))==str(record.get("id")) and row.get("layout")==view["layout"] and (row.get("filter") or "")==view["filter"]]
        if len(matches)!=1: raise SystemExit(f"verified view read-back mismatch: {view['name']}")

expected_state_counts={"labels":15,"issues":32,"hierarchy":31,"project_items":32,"views":3}
for section,count in expected_state_counts.items():
    if len(state[section])!=count: raise SystemExit(f"state count mismatch: {section}")
if set(state["hierarchy"])!={f"{p}->{c}" for p,c in edges}: raise SystemExit("hierarchy state keys mismatch")
print("verified repository=1 labels=15 issues=32 hierarchy=31 project_items=32 views=3")
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
unverified, any view lacks either verification or `manual_required=true`, a
failure remains current, or the manifest checksum changed.

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
| 7 | Reconcile and record 15 labels | REMOTE WRITE | D |
| 8–9 | Create/link Project; create/extract fields and options | REMOTE WRITE | D |
| 10–11 | Create/record master, 8 umbrellas, 23 children | REMOTE WRITE | D |
| 12 | Apply and verify 31 hierarchy relationships | REMOTE WRITE | D |
| 13–14 | Add 32 Project items and populate three fields | REMOTE WRITE | D |
| 15 | Configure supported views or record exact manual boundary | REMOTE or manual WRITE | D |
| 16 | Compare all managed remote resources with the manifest | READ-ONLY | D completion |
| 17–18 | Finalize checksummed state or resume additively | LOCAL WRITE / READ-ONLY | Evidence |

No command in this document authorizes its own execution. Gate approval must
be current and explicit immediately before the corresponding remote mutation.
