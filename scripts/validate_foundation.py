"""Validate repository foundation and backlog contracts using the standard library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKLOG_ROOT = REPOSITORY_ROOT / "docs" / "backlog"

REQUIRED_ISSUE_SECTIONS = (
    "Objective",
    "Rationale",
    "Parent identifier",
    "Source task",
    "Traceability",
    "Prerequisites",
    "Likely files",
    "Implementation boundary",
    "MUST scope",
    "Explicit non-goals",
    "Acceptance criteria",
    "Validation commands",
    "Expected evidence",
    "Fallback and status consequence",
    "Stop condition",
    "Definition of ready",
    "Definition of done",
    "Labels",
    "Estimate",
)
REQUIRED_UMBRELLA_SECTIONS = (
    "Objective",
    "Child epics",
    "Boundary",
    "Acceptance contract",
    "Validation",
    "Labels",
)

EXPECTED_TARGETS = {
    "acceptance",
    "baseline",
    "data",
    "demo",
    "evaluate",
    "help",
    "lint",
    "serve",
    "setup",
    "test",
    "train",
}
EXPECTED_TASK_IDS = {f"T-{index:03d}" for index in range(1, 9)}
EXPECTED_FR_IDS = {f"FR-{index:03d}" for index in range(1, 11)}
EXPECTED_NFR_IDS = {f"NFR-{index:03d}" for index in range(1, 11)}
EXPECTED_AC_IDS = {f"AC-{index:03d}" for index in range(1, 15)}
EXPECTED_TRACEABILITY_IDS = EXPECTED_TASK_IDS | EXPECTED_FR_IDS | EXPECTED_NFR_IDS | EXPECTED_AC_IDS

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME|CHANGEME|REPLACE_ME|YOUR_[A-Z0-9_]*)\b")
SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
)

GitExpectation = Literal["any", "uninitialized", "local-only"]


@dataclass(frozen=True)
class GitState:
    """Read-only observations about Git metadata rooted at the repository."""

    functional_repository: bool
    head_exists: bool
    index_exists: bool
    object_database_exists: bool
    remotes: tuple[str, ...]
    branch: str | None
    upstream: str | None


def _load_json(path: Path) -> dict[str, object]:
    value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise AssertionError(f"{path.relative_to(REPOSITORY_ROOT)} must contain a JSON object")
    return cast(dict[str, object], value)


def _objects(value: object, name: str) -> list[dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AssertionError(f"{name} must be a list of objects")
    return cast(list[dict[str, object]], value)


def _strings(value: object, name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssertionError(f"{name} must be a list of strings")
    return cast(list[str], value)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise AssertionError(f"{name} must be a non-empty string")
    return value


def _authored_text_files() -> Iterable[Path]:
    direct = (
        REPOSITORY_ROOT / "AGENTS.md",
        REPOSITORY_ROOT / "CLAUDE.md",
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "Makefile",
        REPOSITORY_ROOT / "pyproject.toml",
        REPOSITORY_ROOT / ".env.example",
    )
    yield from direct
    for root_name in ("configs", "src", "scripts", "tests"):
        yield from (REPOSITORY_ROOT / root_name).rglob("*")
    # Only the contract READMEs are authored under the generated roots; model
    # payloads and JSON reports written there are build output, and scanning
    # them for authoring placeholders is meaningless.
    for root_name in ("artifacts", "data", "reports"):
        yield REPOSITORY_ROOT / root_name / "README.md"
    yield from BACKLOG_ROOT.rglob("*")
    for name in ("OPERATIONS.md", "IMPLEMENTATION_STATUS.md", "LIMITATIONS.md"):
        yield REPOSITORY_ROOT / "docs" / name
    yield from (REPOSITORY_ROOT / ".github").rglob("*")


def validate_toml_and_project() -> None:
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    with (REPOSITORY_ROOT / "configs" / "default.toml").open("rb") as stream:
        config = tomllib.load(stream)

    metadata = cast(dict[str, object], project["project"])
    assert metadata["name"] == "intentguard"
    assert metadata["requires-python"] == ">=3.11,<3.12"
    tool = cast(dict[str, object], project["tool"])
    uv_config = cast(dict[str, object], tool["uv"])
    assert uv_config["required-version"] == "==0.11.8"
    assert cast(dict[str, object], uv_config["sources"])["torch"] == [
        {"index": "pytorch-cpu"}
    ]
    data = cast(dict[str, object], config["data"])
    assert data["dataset_id"] == "PolyAI/banking77"
    assert data["dataset_revision"] == "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
    assert data["validation_fraction"] == 0.15
    # E04 resolved the base-model pin. The revision must be an immutable 40-hex
    # commit rather than a mutable ref such as `main`, which would silently change
    # the trained weights between runs while leaving provenance unchanged.
    model = cast(dict[str, object], config["model"])
    assert model["base_model_id"] == "distilbert/distilbert-base-uncased"
    revision = model["base_model_revision"]
    assert isinstance(revision, str)
    assert len(revision) == 40
    assert set(revision) <= set("0123456789abcdef"), revision
    print("PASSED: TOML parsing and pyproject/configuration contract")


def _recipe_lines(makefile: str, target: str) -> list[str]:
    """Return the tab-indented recipe lines belonging to one Make target."""

    lines: list[str] = []
    collecting = False
    for line in makefile.splitlines():
        if line.startswith(f"{target}:"):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                lines.append(line.strip())
                continue
            if line.strip():
                break
    return lines


def validate_make_contract() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
    targets = {line.split(":", maxsplit=1)[0] for line in makefile.splitlines() if ": ##" in line}
    assert targets == EXPECTED_TARGETS, f"Unexpected Make targets: {sorted(targets)}"
    assert "uv run --locked python scripts/prepare_data.py" in makefile
    assert "uv run --locked python scripts/train_baseline.py" in makefile
    assert "uv run --locked python scripts/train_transformer.py" in makefile
    assert "uv run --locked python scripts/evaluate.py" in makefile
    assert "uv run --locked python -m intentguard.app" in makefile
    assert "uv run --locked python scripts/demo.py" in makefile
    assert "uv run --locked python scripts/validate_acceptance.py" in makefile
    # U06 is wired now, so no placeholder may remain for any umbrella: every declared
    # command must either do its real work or be absent, never exit zero while
    # pretending. This assertion was inverted for U06 in the same change that wired
    # `serve` and `demo`, because leaving it as-is would have failed `make lint`.
    for umbrella in ("U04", "U05", "U06", "U07"):
        assert f"Not implemented — tracked by {umbrella}" not in makefile
    # Serving must load an artifact, never create one. A `serve` or `demo` recipe that
    # reached for a training or data script would make the strict demo self-fulfilling,
    # so their recipe bodies are read and checked rather than assumed.
    for target in ("serve", "demo"):
        for line in _recipe_lines(makefile, target):
            for forbidden in (
                "scripts/prepare_data.py",
                "scripts/train_baseline.py",
                "scripts/train_transformer.py",
                "scripts/evaluate.py",
            ):
                assert forbidden not in line, f"{target} must not run {forbidden}"
    print("PASSED: developer command presence, no placeholders, and non-training serving")


def validate_backlog() -> tuple[dict[str, object], set[str]]:
    manifest = _load_json(BACKLOG_ROOT / "github-manifest.json")
    issues = _objects(manifest.get("issues"), "issues")
    issue_ids = [_string(issue.get("id"), "issue.id") for issue in issues]
    titles = [_string(issue.get("title"), "issue.title") for issue in issues]
    types = [_string(issue.get("type"), "issue.type") for issue in issues]
    orders = [issue.get("creation_order") for issue in issues]

    migration = cast(dict[str, object], manifest.get("migration", {}))
    assert manifest.get("schema_version") == 2
    assert migration == {
        "migration_id": "hierarchy-v2",
        "from_schema_version": 1,
        "to_schema_version": 2,
        "migration_from_manifest_sha256": (
            "c8c1966a7d512f284bc9a96833b50cfa383b6c06ca30f54cb4401df40f335ed8"
        ),
        "hierarchy_version": 2,
        "milestone_id": "M1",
        "legacy_master_issue": "MVP",
        "legacy_umbrella_prefix": "U",
        "legacy_child_prefix": "C",
        "canonical_umbrella_prefix": "W",
        "canonical_epic_prefix": "E",
        "canonical_subtask_prefix": "S",
        "old_identifier_policy": (
            "Retain old U/C identifiers on their canonical E/S records; "
            "no remote master issue is created."
        ),
        "old_inventory": {
            "milestones": 0, "master_issues": 1, "umbrellas": 8, "children": 23,
            "total_issues": 32, "relationships": 31, "project_items": 32,
            "managed_labels": 15,
        },
        "new_inventory": {
            "milestones": 1, "umbrellas": 3, "epics": 8, "subtasks": 23,
            "total_issues": 34, "relationships": 31, "project_items": 34,
            "managed_labels": 16,
        },
    }
    milestone = cast(dict[str, object], manifest.get("milestone", {}))
    milestone_source = REPOSITORY_ROOT / _string(
        milestone.get("source_file"), "milestone.source_file"
    )
    assert milestone == {
        "id": "M1",
        "title": "IntentGuard Weekend MVP",
        "source_file": "docs/backlog/MASTER_ISSUE.md",
        "source_sha256": hashlib.sha256(milestone_source.read_bytes()).hexdigest(),
        "issue_count": 34,
        "canonical_type": "milestone",
        "deterministic_description_contract": (
            "UTF-8 bytes of source_file, passed unchanged as the milestone description."
        ),
    }
    assert types.count("umbrella") == 3
    assert types.count("epic") == 8
    assert types.count("subtask") == 23
    assert len(issue_ids) == len(set(issue_ids)) == 34
    assert len(titles) == len(set(titles)) == 34
    assert sorted(cast(list[int], orders)) == list(range(1, 35))

    issue_id_set = set(issue_ids)
    expected_umbrellas = {f"W{index:02d}" for index in range(1, 4)}
    expected_epics = {f"E{index:02d}" for index in range(1, 9)}
    expected_subtasks = {
        *(f"S{umbrella:02d}.{child}" for umbrella in range(1, 7) for child in range(1, 4)),
        "S07.1", "S07.2", "S08.1", "S08.2", "S08.3",
    }
    assert issue_id_set == expected_umbrellas | expected_epics | expected_subtasks

    for issue in issues:
        issue_id = _string(issue.get("id"), "issue.id")
        title = _string(issue.get("title"), "issue.title")
        body_path = REPOSITORY_ROOT / _string(issue.get("body_file"), "issue.body_file")
        assert body_path.is_file(), f"Missing issue body for {issue_id}"
        body = body_path.read_text(encoding="utf-8")
        assert body.startswith(f"# {title}\n"), f"Title mismatch in {body_path}"
        required_sections = (
            REQUIRED_UMBRELLA_SECTIONS
            if issue.get("type") == "umbrella"
            else REQUIRED_ISSUE_SECTIONS
        )
        for section in required_sections:
            assert f"## {section}\n" in body, f"{issue_id} missing section: {section}"

    relationships = _objects(manifest.get("relationships"), "relationships")
    declared_parent: dict[str, str] = {}
    for relationship in relationships:
        parent = _string(relationship.get("parent"), "relationship.parent")
        child = _string(relationship.get("child"), "relationship.child")
        assert child not in declared_parent, f"Duplicate relationship for {child}"
        declared_parent[child] = parent
    assert len(declared_parent) == 31
    for issue in issues:
        issue_id = _string(issue.get("id"), "issue.id")
        assert issue.get("milestone_id") == "M1"
        assert "milestone" not in issue
        if issue.get("type") == "umbrella":
            assert issue.get("parent") is None
        else:
            assert declared_parent[issue_id] == issue.get("parent")
    relationships_by_type = {"umbrella-epic": 0, "epic-subtask": 0}
    issue_by_id = {issue["id"]: issue for issue in issues}
    for relationship in relationships:
        relationship_type = relationship.get("relationship_type")
        assert relationship_type in relationships_by_type
        parent_issue = issue_by_id[relationship["parent"]]
        child_record = issue_by_id[relationship["child"]]
        expected_type = (
            "umbrella-epic"
            if parent_issue["type"] == "umbrella" and child_record["type"] == "epic"
            else "epic-subtask"
        )
        assert relationship_type == expected_type
        relationships_by_type[relationship_type] += 1
    assert relationships_by_type == {"umbrella-epic": 8, "epic-subtask": 23}

    direct_total = 0.0
    for issue in issues:
        children = [row["child"] for row in relationships if row["parent"] == issue["id"]]
        if issue["type"] == "subtask":
            assert issue.get("estimate_kind") == "direct"
            assert issue.get("expected_rollup") is None
            assert issue.get("rollup_children") == []
            direct_total += float(cast(int | float, issue["estimate_hours"]))
        else:
            assert issue.get("estimate_kind") == "derived-rollup"
            assert issue.get("rollup_children") == children
            expected_rollup = sum(
                float(cast(
                    int | float,
                    issue_by_id[child]["estimate_hours"]
                    if issue_by_id[child]["type"] == "subtask"
                    else issue_by_id[child]["expected_rollup"],
                ))
                for child in children
            )
            assert issue.get("expected_rollup") == expected_rollup
            assert issue.get("estimate_hours") == expected_rollup
    assert direct_total == 16.0
    project_items = _objects(manifest.get("project_items"), "project_items")
    assert len(project_items) == 34
    for item in project_items:
        issue = issue_by_id[item["id"]]
        assert isinstance(item.get("estimate_hours"), (int, float))
        assert not isinstance(item.get("estimate_hours"), bool)
        assert item.get("estimate_kind") == issue.get("estimate_kind")
        assert item.get("expected_rollup") == issue.get("expected_rollup")
        assert item.get("rollup_children") == issue.get("rollup_children")

    labels = _objects(manifest.get("labels"), "labels")
    assert len(labels) == 16
    assert len({_string(label.get("name"), "label.name") for label in labels}) == 16
    print(
        "PASSED: JSON manifest parsing, M1 + 3 + 8 + 23 backlog count, "
        "titles, bodies, and hierarchy"
    )
    return manifest, issue_id_set


def validate_traceability(issue_ids: set[str]) -> None:
    traceability = _load_json(BACKLOG_ROOT / "traceability.json")
    ownership = _objects(traceability.get("ownership"), "ownership")
    identifiers = [_string(row.get("identifier"), "ownership.identifier") for row in ownership]

    assert len(identifiers) == len(set(identifiers)) == 42
    assert set(identifiers) == EXPECTED_TRACEABILITY_IDS
    for row in ownership:
        umbrella = _string(row.get("umbrella"), "ownership.umbrella")
        epic = _string(row.get("epic"), "ownership.epic")
        subtask = _string(row.get("subtask"), "ownership.subtask")
        assert umbrella in issue_ids and epic in issue_ids and subtask in issue_ids
        assert umbrella.startswith("W") and epic.startswith("E") and subtask.startswith("S")
        _string(row.get("implementation_path"), "ownership.implementation_path")
        _string(row.get("validation_command"), "ownership.validation_command")
        _string(row.get("expected_evidence"), "ownership.expected_evidence")
    print("PASSED: exactly one primary owner for all 42 T/FR/NFR/AC identifiers")


def validate_markdown_links() -> None:
    failures: list[str] = []
    for path in REPOSITORY_ROOT.rglob("*.md"):
        if ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = target.split("#", maxsplit=1)[0]
            if path_part and not (path.parent / path_part).resolve().exists():
                failures.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {target}")
    assert not failures, "Broken Markdown links:\n" + "\n".join(failures)
    print("PASSED: local Markdown-link validation")


def validate_gate_d_preflight() -> None:
    runbook = (BACKLOG_ROOT / "GITHUB_EXECUTION_PLAN.md").read_text(encoding="utf-8")
    preflight = runbook.find("ig_gate_d_migration_preflight")
    first_gate_d_write = runbook.find("## 7. Gate D labels")
    assert preflight >= 0 and first_gate_d_write >= 0 and preflight < first_gate_d_write
    assert "STATE_MIGRATION_REQUIRED" in runbook[preflight:first_gate_d_write]
    assert "migration_history" in runbook[preflight:first_gate_d_write]
    assert "git ls-remote" in runbook[preflight:first_gate_d_write]
    assert "ig_gate_d_migration_preflight || exit" in runbook
    assert "ig_migrate_state_after_remote_readback" in runbook
    assert "old_state_bytes_sha" in runbook
    assert "state_sha256" in runbook
    print("PASSED: executable Gate D migration preflight and state-migration contract")


def assert_generated_output_is_untracked(root: Path) -> None:
    """Assert a generated root holds only its README and untracked build output.

    The contract is that generated artifacts and reports are never committed, not
    that they never exist. A successful `make baseline` legitimately populates
    these directories, so this checks tracking status rather than emptiness.
    """

    relative_root = root.relative_to(REPOSITORY_ROOT).as_posix()
    tracked_result = _run_git(REPOSITORY_ROOT, "ls-files", "--", relative_root)
    if tracked_result.returncode != 0:
        # No functional repository: nothing can be tracked, so the on-disk
        # README check above is already the whole contract.
        return

    tracked = {line for line in tracked_result.stdout.splitlines() if line}
    assert tracked == {f"{relative_root}/README.md"}, (
        f"Generated output under {relative_root} must stay untracked: {sorted(tracked)}"
    )


def validate_generated_roots_and_specification() -> None:
    ignore_lines = {
        line.strip()
        for line in (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    required_ignore_lines = {
        ".env",
        ".env.*",
        "!.env.example",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
        "*.pt",
        "*.bin",
        "*.safetensors",
        ".cache/",
        ".huggingface/",
        "data/*",
        "!data/README.md",
        "artifacts/*",
        "!artifacts/README.md",
        "reports/*",
        "!reports/README.md",
    }
    assert required_ignore_lines <= ignore_lines, "Required .gitignore rules are missing"

    assert (REPOSITORY_ROOT / "data" / "README.md").is_file()
    for name in ("artifacts", "reports"):
        root = REPOSITORY_ROOT / name
        assert (root / "README.md").is_file(), f"Missing contract README under {name}"
        assert_generated_output_is_untracked(root)

    authoritative = REPOSITORY_ROOT / "docs" / "specification"
    assert (authoritative / "docs" / "REQUIREMENTS.md").is_file()
    unique_spec_names = {
        "ARCHITECTURE.md",
        "FINAL_VALIDATION.md",
        "GITHUB_PRESENTATION.md",
        "INTERFACE_CONTRACT.md",
        "ML_SYSTEM_DESIGN.md",
        "PRODUCTION_READINESS.md",
        "PROJECT_BRIEF.md",
        "REQUIREMENTS.md",
        "SCOPE_CONTROL.md",
        "SCOPE_REVIEW.md",
        "TEST_STRATEGY.md",
    }
    duplicates = [
        path
        for path in REPOSITORY_ROOT.rglob("*.md")
        if path.name in unique_spec_names and authoritative not in path.parents
    ]
    assert not duplicates, f"Potential duplicated specification files: {duplicates}"
    print("PASSED: ignore-rule/generated-artifact scan and sole specification location")


def validate_placeholders_and_secrets() -> None:
    placeholders: list[str] = []
    authored_paths = {
        path
        for path in _authored_text_files()
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.resolve() != Path(__file__).resolve()
    }
    for path in sorted(authored_paths):
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER.search(text):
            placeholders.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert not placeholders, f"Unresolved generic placeholders: {placeholders}"

    config_text = (REPOSITORY_ROOT / "configs" / "default.toml").read_text(encoding="utf-8")
    # E02 left exactly one `UNRESOLVED` gate, the base-model revision. E04 pinned
    # it, so no unresolved value may remain: a reintroduced placeholder would mean
    # some model-affecting input is no longer frozen before training.
    assert config_text.count('= "UNRESOLVED"') == 0

    secret_hits: list[str] = []
    for path in REPOSITORY_ROOT.rglob("*"):
        skipped_part = any(part in {".git", ".venv", "__pycache__"} for part in path.parts)
        if not path.is_file() or skipped_part:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            secret_hits.append(str(path.relative_to(REPOSITORY_ROOT)))
    assert not secret_hits, f"Potential secrets detected: {secret_hits}"
    print("PASSED: placeholder scan (no unresolved gates remain) and secret-pattern scan")


def _run_git(repository_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run one read-only Git inspection command."""

    return subprocess.run(
        ["git", "-C", str(repository_root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _configured_remotes_from_file(config_path: Path) -> tuple[str, ...]:
    if not config_path.is_file():
        return ()
    config_text = config_path.read_text(encoding="utf-8")
    remote_names = re.findall(
        r'^\s*\[remote\s+"([^"]+)"\]\s*$',
        config_text,
        re.MULTILINE,
    )
    return tuple(sorted(set(remote_names)))


def inspect_git_state(repository_root: Path = REPOSITORY_ROOT) -> GitState:
    """Inspect repository-local Git state without changing it."""

    root = repository_root.resolve()
    top_level_result = _run_git(root, "rev-parse", "--show-toplevel")
    functional_repository = (
        top_level_result.returncode == 0
        and Path(top_level_result.stdout.strip()).resolve() == root
    )

    git_directory = root / ".git"
    if functional_repository:
        git_directory_result = _run_git(root, "rev-parse", "--absolute-git-dir")
        if git_directory_result.returncode != 0 or not git_directory_result.stdout.strip():
            raise AssertionError(
                "Git repository is functional but its metadata directory is unavailable"
            )
        git_directory = Path(git_directory_result.stdout.strip())

    head_exists = (git_directory / "HEAD").exists()
    index_exists = (git_directory / "index").exists()
    object_database_exists = (git_directory / "objects").is_dir()

    remotes = _configured_remotes_from_file(git_directory / "config")
    branch: str | None = None
    upstream: str | None = None
    if functional_repository:
        remote_result = _run_git(root, "remote")
        if remote_result.returncode != 0:
            raise AssertionError(f"Unable to inspect Git remotes: {remote_result.stderr.strip()}")
        remotes = tuple(sorted(line for line in remote_result.stdout.splitlines() if line))

        branch_result = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
        if branch_result.returncode == 0:
            branch = branch_result.stdout.strip() or None

        upstream_result = _run_git(
            root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
        if upstream_result.returncode == 0:
            upstream = upstream_result.stdout.strip() or None

    return GitState(
        functional_repository=functional_repository,
        head_exists=head_exists,
        index_exists=index_exists,
        object_database_exists=object_database_exists,
        remotes=remotes,
        branch=branch,
        upstream=upstream,
    )


def assert_git_state(state: GitState, expected: GitExpectation) -> None:
    """Assert that read-only Git observations match the requested lifecycle boundary."""

    violations: list[str] = []
    if expected == "uninitialized":
        if state.functional_repository:
            violations.append("a functional Git repository exists")
        if state.head_exists:
            violations.append("HEAD metadata exists")
        if state.index_exists:
            violations.append("an index exists")
        if state.object_database_exists:
            violations.append("an object database exists")
        if state.remotes:
            violations.append(f"configured remotes exist: {', '.join(state.remotes)}")
    elif expected == "local-only":
        if not state.functional_repository:
            violations.append("no functional Git repository exists")
        if not state.head_exists:
            violations.append("HEAD metadata is missing")
        if not state.object_database_exists:
            violations.append("the object database is missing")
        if state.branch != "main":
            violations.append(f"current branch is {state.branch!r}, not 'main'")
        if state.remotes:
            violations.append(f"configured remotes exist: {', '.join(state.remotes)}")
        if state.upstream is not None:
            violations.append(f"upstream tracking branch exists: {state.upstream}")

    assert not violations, (
        f"Expected Git state {expected!r} did not match: " + "; ".join(violations)
    )


def validate_git_boundary(expected: GitExpectation) -> None:
    state = inspect_git_state()
    assert_git_state(state, expected)
    observed = "initialized" if state.functional_repository else "uninitialized"
    print(f"PASSED: expected Git state {expected!r} validated (observed: {observed})")


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-git-state",
        choices=("any", "uninitialized", "local-only"),
        default="any",
        help="required repository lifecycle state (default: any)",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> None:
    parsed = parse_arguments(arguments)
    expected_git_state = cast(GitExpectation, parsed.expect_git_state)
    validate_toml_and_project()
    validate_make_contract()
    _, issue_ids = validate_backlog()
    validate_traceability(issue_ids)
    validate_markdown_links()
    validate_gate_d_preflight()
    validate_generated_roots_and_specification()
    validate_placeholders_and_secrets()
    validate_git_boundary(expected_git_state)
    print(f"PASSED: foundation validation complete (expected Git state: {expected_git_state})")


if __name__ == "__main__":
    main()
