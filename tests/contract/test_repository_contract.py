import subprocess
import sys
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Protocol, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class _FoundationValidator(Protocol):
    def main(self, arguments: list[str] | None = None) -> None: ...

    def parse_arguments(self, arguments: list[str] | None = None) -> object: ...

    def inspect_git_state(self, repository_root: Path = REPOSITORY_ROOT) -> object: ...

    def assert_git_state(self, state: object, expected: str) -> None: ...

    def assert_generated_output_is_untracked(self, root: Path) -> None: ...


def _load_foundation_validator() -> _FoundationValidator:
    validator_path = REPOSITORY_ROOT / "scripts" / "validate_foundation.py"
    specification = spec_from_file_location("validate_foundation", validator_path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return cast(_FoundationValidator, module)


VALIDATOR = _load_foundation_validator()


def _run_git(
    repository_root: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=check,
        capture_output=True,
        text=True,
    )


def _git_state_snapshot(repository_root: Path) -> dict[str, str]:
    git_directory = repository_root / ".git"
    upstream = _run_git(
        repository_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    )
    status = _run_git(
        repository_root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    return {
        "head": _run_git(repository_root, "rev-parse", "HEAD").stdout.strip(),
        "branch": _run_git(repository_root, "branch", "--show-current").stdout.strip(),
        "config": sha256((git_directory / "config").read_bytes()).hexdigest(),
        "index": sha256((git_directory / "index").read_bytes()).hexdigest(),
        "remotes": _run_git(repository_root, "remote").stdout,
        "upstream_returncode": str(upstream.returncode),
        "upstream": upstream.stdout,
        "status": status.stdout,
    }


@pytest.fixture
def local_only_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2000-01-01T00:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2000-01-01T00:00:00+00:00")

    repository_root = tmp_path / "local-only-repository"
    repository_root.mkdir()
    _run_git(repository_root, "init", "--initial-branch=main")
    _run_git(repository_root, "config", "--local", "user.name", "IntentGuard Test")
    _run_git(
        repository_root,
        "config",
        "--local",
        "user.email",
        "intentguard-tests@example.invalid",
    )
    (repository_root / "README.md").write_text("# Isolated Git fixture\n", encoding="utf-8")
    _run_git(repository_root, "add", "--", "README.md")
    _run_git(repository_root, "-c", "commit.gpgSign=false", "commit", "-m", "test fixture")

    assert _run_git(repository_root, "branch", "--show-current").stdout.strip() == "main"
    assert _run_git(repository_root, "rev-list", "--count", "HEAD").stdout.strip() == "1"
    assert _run_git(repository_root, "remote").stdout == ""
    assert _run_git(
        repository_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{upstream}",
        check=False,
    ).returncode != 0
    assert _run_git(
        repository_root, "status", "--porcelain=v1", "--untracked-files=all"
    ).stdout == ""
    return repository_root


def test_authoritative_specification_remains_in_place() -> None:
    specification = REPOSITORY_ROOT / "docs" / "specification"

    assert (specification / "README.md").is_file()
    assert (specification / "docs" / "REQUIREMENTS.md").is_file()
    assert (specification / "docs" / "ARCHITECTURE.md").is_file()


def test_generated_roots_retain_their_contract_readmes() -> None:
    assert (REPOSITORY_ROOT / "data" / "README.md").is_file()
    for name in ("artifacts", "reports"):
        assert (REPOSITORY_ROOT / name / "README.md").is_file()


def test_generated_output_is_never_tracked() -> None:
    """Generated artifacts and reports may exist on disk but must stay untracked.

    `make baseline` legitimately writes into these roots, so the contract is
    about Git tracking, not about the directories being empty.
    """

    for name in ("artifacts", "reports"):
        VALIDATOR.assert_generated_output_is_untracked(REPOSITORY_ROOT / name)


def test_makefile_exposes_the_complete_command_contract() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
    targets = {line.split(":", maxsplit=1)[0] for line in makefile.splitlines() if ": ##" in line}

    assert targets == {
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


def test_implemented_commands_are_wired_to_their_scripts() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "uv run --locked python scripts/prepare_data.py" in makefile
    assert "uv run --locked python scripts/train_baseline.py" in makefile
    assert (REPOSITORY_ROOT / "scripts" / "train_baseline.py").is_file()
    assert "uv run --locked python scripts/train_transformer.py" in makefile
    assert (REPOSITORY_ROOT / "scripts" / "train_transformer.py").is_file()
    assert "uv run --locked python scripts/evaluate.py" in makefile
    assert (REPOSITORY_ROOT / "scripts" / "evaluate.py").is_file()


def test_unimplemented_commands_are_explicit() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    for umbrella in ("U06",):
        assert f"Not implemented — tracked by {umbrella}" in makefile
    # A wired target must not also carry its placeholder, or `make evaluate` would
    # report success while the recipe still contained a deliberate failure.
    for umbrella in ("U03", "U04", "U05"):
        assert f"Not implemented — tracked by {umbrella}" not in makefile


def test_default_any_mode_accepts_initialized_repository() -> None:
    VALIDATOR.main([])


def test_local_only_accepts_initialized_main_repository_without_remote(
    local_only_repository: Path,
) -> None:
    VALIDATOR.assert_git_state(
        VALIDATOR.inspect_git_state(local_only_repository), "local-only"
    )


def test_uninitialized_rejects_functional_repository() -> None:
    with pytest.raises(AssertionError, match="functional Git repository exists"):
        VALIDATOR.assert_git_state(VALIDATOR.inspect_git_state(REPOSITORY_ROOT), "uninitialized")


def test_uninitialized_accepts_directory_without_git_metadata(tmp_path: Path) -> None:
    VALIDATOR.assert_git_state(VALIDATOR.inspect_git_state(tmp_path), "uninitialized")


def test_invalid_git_state_argument_fails() -> None:
    with pytest.raises(SystemExit) as error:
        VALIDATOR.parse_arguments(["--expect-git-state", "invalid"])

    assert error.value.code == 2


def test_git_validation_modes_do_not_modify_git_state(
    local_only_repository: Path,
) -> None:
    before = _git_state_snapshot(local_only_repository)
    state = VALIDATOR.inspect_git_state(local_only_repository)

    VALIDATOR.assert_git_state(state, "any")
    VALIDATOR.assert_git_state(state, "local-only")
    with pytest.raises(AssertionError):
        VALIDATOR.assert_git_state(state, "uninitialized")

    assert _git_state_snapshot(local_only_repository) == before
