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


def _load_foundation_validator() -> _FoundationValidator:
    validator_path = REPOSITORY_ROOT / "scripts" / "validate_foundation.py"
    specification = spec_from_file_location("validate_foundation", validator_path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return cast(_FoundationValidator, module)


VALIDATOR = _load_foundation_validator()


def _git_metadata_snapshot() -> dict[str, str]:
    git_directory = REPOSITORY_ROOT / ".git"
    snapshot: dict[str, str] = {}
    for path in sorted(git_directory.rglob("*")):
        relative_path = str(path.relative_to(git_directory))
        if path.is_file():
            snapshot[relative_path] = sha256(path.read_bytes()).hexdigest()
        elif path.is_dir():
            snapshot[f"{relative_path}/"] = "directory"
    return snapshot


def test_authoritative_specification_remains_in_place() -> None:
    specification = REPOSITORY_ROOT / "docs" / "specification"

    assert (specification / "README.md").is_file()
    assert (specification / "docs" / "REQUIREMENTS.md").is_file()
    assert (specification / "docs" / "ARCHITECTURE.md").is_file()


def test_generated_roots_retain_only_their_contract_readmes() -> None:
    for name in ("data", "artifacts", "reports"):
        entries = sorted(path.name for path in (REPOSITORY_ROOT / name).iterdir())
        assert entries == ["README.md"]


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


def test_unimplemented_commands_are_explicit() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    for umbrella in ("U02", "U03", "U04", "U05", "U06"):
        assert f"Not implemented — tracked by {umbrella}" in makefile


def test_default_any_mode_accepts_initialized_repository() -> None:
    VALIDATOR.main([])


def test_local_only_accepts_initialized_main_repository_without_remote() -> None:
    VALIDATOR.assert_git_state(VALIDATOR.inspect_git_state(REPOSITORY_ROOT), "local-only")


def test_uninitialized_rejects_functional_repository() -> None:
    with pytest.raises(AssertionError, match="functional Git repository exists"):
        VALIDATOR.assert_git_state(VALIDATOR.inspect_git_state(REPOSITORY_ROOT), "uninitialized")


def test_uninitialized_accepts_directory_without_git_metadata(tmp_path: Path) -> None:
    VALIDATOR.assert_git_state(VALIDATOR.inspect_git_state(tmp_path), "uninitialized")


def test_invalid_git_state_argument_fails() -> None:
    with pytest.raises(SystemExit) as error:
        VALIDATOR.parse_arguments(["--expect-git-state", "invalid"])

    assert error.value.code == 2


def test_git_validation_modes_do_not_modify_git_state() -> None:
    before = _git_metadata_snapshot()
    state = VALIDATOR.inspect_git_state(REPOSITORY_ROOT)

    VALIDATOR.assert_git_state(state, "any")
    VALIDATOR.assert_git_state(state, "local-only")
    with pytest.raises(AssertionError):
        VALIDATOR.assert_git_state(state, "uninitialized")

    assert _git_metadata_snapshot() == before
