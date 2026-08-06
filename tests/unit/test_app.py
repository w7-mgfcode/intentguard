"""Serving entry-point settings and the demo's own helpers (S06.3).

Split from the real-artifact suites deliberately: everything here runs without the
sealed bundle, so CI covers the settings resolution, the fixture lookup, and the
Makefile/serving contract even on a machine that has never trained. `build_app` itself
needs weights and is exercised by `make demo` and `tests/integration/test_api.py`.
"""

from __future__ import annotations

import json
import socket
import sys
from contextlib import closing
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest

from intentguard.app import (
    CONFIG_PATH,
    DEFAULT_HOST,
    DEFAULT_LOG_LEVEL,
    DEFAULT_PORT,
    HOST_VARIABLE,
    LOG_LEVEL_VARIABLE,
    PORT_VARIABLE,
    ServingError,
    resolve_serving_settings,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load_demo() -> ModuleType:
    """Import the demo script without running it; `main` is guarded.

    Loaded by file location under its own stem, matching the other script suites.
    Importing it as `scripts.demo` would give the same file two module names —
    `demo` from `mypy src scripts tests` and `scripts.demo` from here — which mypy
    rejects outright.
    """

    specification = spec_from_file_location("demo", REPOSITORY_ROOT / "scripts" / "demo.py")
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


DEMO = _load_demo()


# --------------------------------------------------------------------------------
# Serving settings
# --------------------------------------------------------------------------------


def test_defaults_are_loopback_and_the_documented_port() -> None:
    settings = resolve_serving_settings({})

    assert settings.host == DEFAULT_HOST == "127.0.0.1"
    assert settings.port == DEFAULT_PORT == 8000
    assert settings.log_level == DEFAULT_LOG_LEVEL


def test_the_default_host_is_not_all_interfaces() -> None:
    """Binding 0.0.0.0 by default would expose an unauthenticated classifier."""

    assert resolve_serving_settings({}).host not in ("0.0.0.0", "::", "")


def test_environment_overrides_are_applied() -> None:
    settings = resolve_serving_settings(
        {HOST_VARIABLE: "127.0.0.9", PORT_VARIABLE: "9101", LOG_LEVEL_VARIABLE: "DEBUG"}
    )

    assert (settings.host, settings.port, settings.log_level) == ("127.0.0.9", 9101, "DEBUG")


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_blank_values_fall_back_rather_than_producing_an_empty_host(value: str) -> None:
    # `int("")` raises and an empty host binds nothing useful, so a variable exported
    # without a value must behave as though it were unset.
    settings = resolve_serving_settings(
        {HOST_VARIABLE: value, PORT_VARIABLE: value, LOG_LEVEL_VARIABLE: value}
    )

    assert (settings.host, settings.port, settings.log_level) == (
        DEFAULT_HOST,
        DEFAULT_PORT,
        DEFAULT_LOG_LEVEL,
    )


@pytest.mark.parametrize("value", ["http", "8000.5", "80 00", "-", "0x1f90"])
def test_a_non_integer_port_is_refused_by_name(value: str) -> None:
    with pytest.raises(ServingError, match=PORT_VARIABLE):
        resolve_serving_settings({PORT_VARIABLE: value})


@pytest.mark.parametrize("value", ["0", "-1", "65536", "99999"])
def test_an_out_of_range_port_is_refused(value: str) -> None:
    """Port 0 is excluded on purpose: it binds an arbitrary port nobody can predict."""

    with pytest.raises(ServingError, match="between 1 and 65535"):
        resolve_serving_settings({PORT_VARIABLE: value})


@pytest.mark.parametrize("value", ["1", "65535", "8080"])
def test_boundary_ports_are_accepted(value: str) -> None:
    assert resolve_serving_settings({PORT_VARIABLE: value}).port == int(value)


def test_the_configuration_path_is_repository_relative_and_present() -> None:
    """Resolved from the module, not the cwd, so `make serve` works from anywhere."""

    assert CONFIG_PATH == REPOSITORY_ROOT / "configs" / "default.toml"
    assert CONFIG_PATH.is_file()


# --------------------------------------------------------------------------------
# The command surface: U06 is wired, and serving cannot train
# --------------------------------------------------------------------------------


def _recipe(target: str) -> list[str]:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
    lines: list[str] = []
    collecting = False
    for line in makefile.splitlines():
        if line.startswith(f"{target}:"):
            collecting = True
            continue
        if collecting:
            if line.startswith("\t"):
                lines.append(line.strip())
            elif line.strip():
                break
    return lines


def test_serve_and_demo_no_longer_declare_placeholders() -> None:
    makefile = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "Not implemented — tracked by U06" not in makefile
    assert _recipe("serve") == ["uv run --locked python -m intentguard.app"]
    assert _recipe("demo") == ["uv run --locked python scripts/demo.py"]


@pytest.mark.parametrize("target", ["serve", "demo"])
def test_serving_targets_never_invoke_data_or_training_scripts(target: str) -> None:
    """Serving loads an artifact. A demo that could train would prove nothing."""

    body = " ".join(_recipe(target))

    for forbidden in (
        "prepare_data.py",
        "train_baseline.py",
        "train_transformer.py",
        "evaluate.py",
    ):
        assert forbidden not in body


@pytest.mark.parametrize("target", ["serve", "demo"])
def test_serving_targets_use_the_locked_environment(target: str) -> None:
    for line in _recipe(target):
        assert line.startswith("uv run --locked ")


def test_the_demo_runs_the_same_entry_point_serve_does() -> None:
    """If these drift, the demo stops being evidence about the shipped serving path."""

    demo_source = (REPOSITORY_ROOT / "scripts" / "demo.py").read_text(encoding="utf-8")

    assert '"-m", "intentguard.app"' in demo_source
    assert "-m intentguard.app" in " ".join(_recipe("serve"))


def test_serving_code_cannot_reach_a_fitting_or_threshold_selecting_function() -> None:
    """A structural check, not a promise in a docstring.

    `app.py` is the whole serving entry point, so if it cannot name `select_threshold`
    or a training routine, `make serve` has no path to one.
    """

    source = (REPOSITORY_ROOT / "src" / "intentguard" / "app.py").read_text(encoding="utf-8")

    for forbidden in ("select_threshold", "fit_pipeline", "train_model", "save_artifact"):
        assert forbidden not in source


# --------------------------------------------------------------------------------
# The demo's helpers, without starting a service
# --------------------------------------------------------------------------------


def test_the_abstention_fixture_row_is_present_and_is_the_measured_one() -> None:
    """The demo reads this row rather than hardcoding its text.

    Pinned here because the E05 evaluation measured *this* row abstaining. If the
    fixture were reordered or reworded, the demo would silently start demonstrating a
    text whose behaviour nobody measured.
    """

    assert DEMO.read_fixture_text(DEMO.ABSTAIN_FIXTURE_ID) == (
        "What is the weather forecast for Lisbon this weekend?"
    )


def test_an_absent_fixture_row_fails_loudly() -> None:
    with pytest.raises(DEMO.DemoError, match="unsupported-999"):
        DEMO.read_fixture_text("unsupported-999")


def test_the_fixture_rows_all_carry_a_category_and_rationale() -> None:
    """Guards the file the demo depends on, since a malformed row would break it.

    `text` is deliberately exempt from the non-empty check: `unsupported-007` is the
    empty-input degenerate case, and requiring text there would ask the fixture to drop
    the row that exists to prove empty input is handled without a confident label.
    """

    path = REPOSITORY_ROOT / "tests" / "fixtures" / "unsupported_requests.jsonl"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(line) for line in lines]

    assert len(rows) == 12
    for row in rows:
        assert row["request_id"] and row["category"] and row["rationale"]
        assert isinstance(row["text"], str)

    # The demo would send an empty body for this row, which the API's own contract
    # rejects with a 422 — so the demo must not be pointed at it.
    empty = [row["request_id"] for row in rows if not row["text"]]
    assert empty == ["unsupported-007"]
    assert DEMO.ABSTAIN_FIXTURE_ID not in empty


def test_free_port_returns_a_bindable_port() -> None:
    port = DEMO.free_port()

    assert 1024 <= port <= 65535
    # Releasing then rebinding proves the probe closed its socket; a leaked socket
    # would make the child fail to bind with "address already in use".
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as check:
        check.bind(("127.0.0.1", port))


def test_the_demo_asserts_both_decisions_rather_than_only_printing_them() -> None:
    """A transcript that never fails is not evidence.

    AC-013 needs the demo to *require* one accept and one abstain, so the script's
    failure branch is checked to exist rather than trusting that it does.
    """

    source = (REPOSITORY_ROOT / "scripts" / "demo.py").read_text(encoding="utf-8")

    assert 'accepted["decision"] != "accept"' in source
    assert 'abstained["decision"] != "abstain"' in source
    assert "raise DemoError" in source


def test_the_demo_kills_a_service_that_ignores_termination() -> None:
    """Shutdown reliability: a leaked child would hold a port past the make target."""

    source = (REPOSITORY_ROOT / "scripts" / "demo.py").read_text(encoding="utf-8")

    assert "finally:" in source
    assert "process.terminate()" in source
    assert "process.kill()" in source
