#!/usr/bin/env python3
"""Scope and optionally execute one explicitly approved atomic commit flow.

The default mode is read-only. ``--flow-atom`` adds a complete decision flow,
but still stops before mutation unless ``--approve-commit`` is supplied. Push
is a second, explicit approval and is always a normal non-force push.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = (
    re.compile(r"(?:ghp_|github_pat_|sk-)[A-Za-z0-9_\-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{12,}"),
)
CONVENTIONAL = re.compile(r"^[a-z][a-z0-9-]*(?:\([^)]+\))?!?: .{1,72}$")
GENERATED_PREFIXES = (".venv/", "dist/", "data/", "artifacts/", "reports/")


def command(
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, check=False, capture_output=True, text=True, env=env, cwd=cwd
    )
    if check and result.returncode:
        detail = result.stderr.strip().splitlines()[-1:] or result.stdout.strip().splitlines()[-1:]
        suffix = f": {detail[0][:240]}" if detail else ""
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args)}{suffix}")
    return result


def output(*args: str) -> str:
    return command(*args).stdout


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", required=True, help="proposed Conventional Commit subject")
    parser.add_argument("--staged-only", action="store_true", help="review only the staged diff")
    parser.add_argument(
        "--path", action="append", default=[], help="allowed repository-relative path"
    )
    parser.add_argument("--flow-atom", action="store_true", help="run the full gated decision flow")
    parser.add_argument(
        "--approve-commit", action="store_true", help="explicitly authorize one local commit"
    )
    parser.add_argument(
        "--approve-push", action="store_true", help="explicitly authorize one normal origin push"
    )
    return parser.parse_args()


def paths_for(root: Path, staged_only: bool) -> tuple[list[str], list[str], list[str], list[str]]:
    status = output("git", "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    staged = output("git", "diff", "--cached", "--name-only").splitlines()
    unstaged = output("git", "diff", "--name-only").splitlines()
    untracked = [line[3:] for line in status if line.startswith("?? ")]
    changed = sorted(set(staged if staged_only else staged + unstaged + untracked))
    return staged, unstaged, untracked, changed


def inspect_scope(args: argparse.Namespace, root: Path) -> dict[str, object]:
    staged, unstaged, untracked, changed = paths_for(root, args.staged_only)
    allowed = {Path(value).as_posix() for value in args.path}
    unscoped = sorted(set(changed) - allowed) if allowed else []
    missing_allowed = sorted(allowed - set(changed)) if allowed else []
    hygiene_args = ["git", "diff", "--check"]
    if args.staged_only:
        hygiene_args.insert(2, "--cached")
    hygiene = command(*hygiene_args)
    diff_args = ("git", "diff", "--cached") if args.staged_only else ("git", "diff")
    if allowed:
        diff_args = (*diff_args, "--", *sorted(allowed))
    diff = output(*diff_args)
    for path in sorted(allowed & set(untracked)):
        candidate = root / path
        if candidate.is_file():
            diff += f"\n--- untracked {path}\n" + candidate.read_text(encoding="utf-8")
    secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(diff)]
    conflict_markers = bool(re.search(r"^<<<<<<< |^======= $|^>>>>>>> ", diff, re.MULTILINE))
    generated = [
        path
        for path in changed
        if path.startswith(GENERATED_PREFIXES) and not path.endswith("README.md")
    ]
    return {
        "staged_paths": staged,
        "unstaged_paths": unstaged,
        "untracked_paths": untracked,
        "reviewed_paths": changed,
        "unscoped_paths": unscoped,
        "missing_allowed_paths": missing_allowed,
        "generated_paths": generated,
        "secret_pattern_hits": secret_hits,
        "conflict_markers": conflict_markers,
        "hygiene_returncode": hygiene.returncode,
    }


def run_project_checks(root: Path) -> list[dict[str, object]]:
    checks = [
        ("uv lock --check", ("uv", "lock", "--check")),
        ("make lint", ("make", "lint")),
        ("make test", ("make", "test")),
    ]
    results = []
    check_env = os.environ.copy()
    check_env.setdefault("UV_CACHE_DIR", "/tmp/atomic-commit-uv-cache")
    for label, args in checks:
        result = command(*args, check=False, env=check_env, cwd=root)
        results.append(
            {"command": label, "returncode": result.returncode, "passed": result.returncode == 0}
        )
        if result.returncode:
            break
    return results


def gate_failures(scope: dict[str, object], args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if scope["missing_allowed_paths"]:
        failures.append("allow-list paths are not changed")
    if scope["generated_paths"]:
        failures.append("generated artifacts are in the reviewed set")
    if scope["secret_pattern_hits"]:
        failures.append("secret-like content detected")
    if scope["conflict_markers"]:
        failures.append("conflict markers detected")
    if not args.staged_only and scope["staged_paths"]:
        failures.append("staged paths exist; review staged and unstaged scopes separately")
    return failures


def commit_and_verify(args: argparse.Namespace, root: Path) -> dict[str, object]:
    command("git", "add", "--", *args.path)
    staged_scope = inspect_scope(argparse.Namespace(**{**vars(args), "staged_only": True}), root)
    staged_args = argparse.Namespace(**{**vars(args), "staged_only": True})
    failures = gate_failures(staged_scope, staged_args)
    expected_paths = sorted(Path(p).as_posix() for p in args.path)
    if failures or sorted(staged_scope["staged_paths"]) != expected_paths:
        detail = "; ".join(failures or ["staged paths differ from allow-list"])
        raise RuntimeError("staged scope verification failed: " + detail)
    command("git", "commit", "-m", args.message)
    sha = output("git", "rev-parse", "HEAD").strip()
    subject = output("git", "log", "-1", "--format=%s").strip()
    committed = output("git", "show", "--format=", "--name-only", "HEAD").splitlines()
    if subject != args.message or sorted(set(committed)) != expected_paths:
        raise RuntimeError("commit read-back does not match approved subject or paths")
    if output("git", "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise RuntimeError("working tree is not clean after approved commit")
    return {"commit_sha": sha, "commit_subject": subject, "commit_paths": sorted(set(committed))}


def push_and_verify(root: Path, branch: str, expected_sha: str) -> dict[str, object]:
    remotes = output("git", "remote").split()
    if remotes != ["origin"]:
        raise RuntimeError("push requires exactly one remote named origin")
    command("git", "push", "origin", branch)
    remote_sha = output("git", "ls-remote", "origin", f"refs/heads/{branch}").split()[0]
    if remote_sha != expected_sha:
        raise RuntimeError("remote read-back SHA differs from local commit")
    return {"remote_sha": remote_sha, "pushed": True}


def main() -> int:
    args = parse_args()
    if not CONVENTIONAL.fullmatch(args.message):
        print(
            "FAIL: commit subject must match 'type: imperative description' and be <=72 characters",
            file=sys.stderr,
        )
        return 2
    if (args.approve_commit or args.approve_push) and not args.flow_atom:
        print("FAIL: approval flags require --flow-atom", file=sys.stderr)
        return 2
    if args.approve_push and not args.approve_commit:
        print(
            "FAIL: --approve-push requires --approve-commit in the same explicit flow",
            file=sys.stderr,
        )
        return 2
    if args.flow_atom and not args.path:
        print("FAIL: --flow-atom requires an explicit --path allow-list", file=sys.stderr)
        return 2
    root = Path(output("git", "rev-parse", "--show-toplevel").strip())
    scope = inspect_scope(args, root)
    report: dict[str, object] = {
        "repository": str(root),
        "branch": output("git", "branch", "--show-current").strip(),
        "head": output("git", "rev-parse", "HEAD").strip(),
        "message": args.message,
        **scope,
        "remote_names": output("git", "remote").split(),
        "flow_atom": args.flow_atom,
        "approved_commit": args.approve_commit,
        "approved_push": args.approve_push,
    }
    failures = gate_failures(scope, args)
    if args.flow_atom and not failures:
        report["checks"] = run_project_checks(root)
        failures.extend(
            f"check failed: {item['command']}"
            for item in report["checks"]
            if not item["passed"]
        )
    if failures:
        report["decision"] = "BLOCKED"
        report["failures"] = failures
        print(json.dumps(report, indent=2, sort_keys=True))
        print("BLOCKED: " + "; ".join(failures), file=sys.stderr)
        return 1
    if args.flow_atom and args.approve_commit:
        report["commit"] = commit_and_verify(args, root)
        report["head"] = report["commit"]["commit_sha"]
        report["decision"] = "PUSHED" if args.approve_push else "READY_TO_PUSH"
        if args.approve_push:
            report["push"] = push_and_verify(root, report["branch"], report["head"])
            report["decision"] = "PUSHED"
    else:
        report["decision"] = "READY_TO_COMMIT" if args.flow_atom else "REVIEW_ONLY"
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"PASS: {report['decision']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
