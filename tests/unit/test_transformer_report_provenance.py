"""The training report must describe the run that trained, not the run that reports.

`make train` reuses an existing bundle when the run ID already exists, and it
rewrites `training.json` on that path without loading a model. Measuring the
current process there attributes this machine's peak memory, thread count, and
library versions to a run that trained nothing, and the report puts those values
next to `run_id`, `threshold`, and the validation metrics that really do come from
the original run — so a reader cannot tell which fields belong to which machine.

This actually happened: a second `make train` rewrote the committed report's
`peak_memory_bytes` from 2877472768 to 587182080 while the bundle's immutable
`provenance.json` kept the true value. These tests pin the fix.
"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from intentguard.artifacts import ArtifactError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

RECORDED_RUNTIME = {
    "cuda_available": False,
    "device": "cpu",
    "peak_memory_bytes": 2877472768,
    "thread_count": 14,
    "torch_version": "2.13.0+cpu",
    "transformers_version": "5.14.1",
}
RECORDED_DEPENDENCIES = {"torch": "2.13.0+cpu", "transformers": "5.14.1"}
RECORDED_PYTHON = "3.11.15"


def _load_train_transformer() -> ModuleType:
    """Import the orchestration script without running it; `main` is guarded."""

    script_path = REPOSITORY_ROOT / "scripts" / "train_transformer.py"
    specification = spec_from_file_location("train_transformer", script_path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


TRAIN_TRANSFORMER = _load_train_transformer()


class _StubBundle:
    """Only `run_id` and `provenance` are read by the functions under test."""

    def __init__(self, provenance: dict[str, Any]) -> None:
        self.run_id = "intentguard-distilbert-stub-000000000000"
        self.provenance = provenance


def _bundle(**overrides: Any) -> _StubBundle:
    provenance: dict[str, Any] = {
        "runtime": dict(RECORDED_RUNTIME),
        "dependency_versions": dict(RECORDED_DEPENDENCIES),
        "python_version": RECORDED_PYTHON,
    }
    provenance.update(overrides)
    return _StubBundle(provenance)


def test_the_reuse_path_reports_the_recorded_training_runtime() -> None:
    # The whole point of the fix: the value comes from the bundle, so it cannot
    # drift to whatever machine is rebuilding the report.
    assert TRAIN_TRANSFORMER._reused_runtime(_bundle()) == RECORDED_RUNTIME


def test_the_reuse_path_does_not_remeasure_this_process() -> None:
    from intentguard.training import resolve_device, runtime_facts, runtime_payload

    live = runtime_payload(runtime_facts(resolve_device()))
    reused = TRAIN_TRANSFORMER._reused_runtime(_bundle())

    # A stub peak of 2.88 GB is not this test process's peak, so equality here would
    # mean the recorded value was ignored.
    assert reused["peak_memory_bytes"] == RECORDED_RUNTIME["peak_memory_bytes"]
    assert reused["peak_memory_bytes"] != live["peak_memory_bytes"]


def test_the_returned_runtime_is_a_copy_of_the_provenance_block() -> None:
    bundle = _bundle()
    reused = TRAIN_TRANSFORMER._reused_runtime(bundle)
    reused["peak_memory_bytes"] = 1

    # Mutating the report payload must not reach back into the loaded bundle.
    assert bundle.provenance["runtime"]["peak_memory_bytes"] == 2877472768


@pytest.mark.parametrize("value", [None, {}, "cpu", 14])
def test_a_bundle_without_a_recorded_runtime_is_refused(value: Any) -> None:
    # Silently substituting the current machine is what caused the defect, so an
    # unusable record must fail loudly instead.
    with pytest.raises(ArtifactError, match="recorded training runtime"):
        TRAIN_TRANSFORMER._reused_runtime(_bundle(runtime=value))


def test_recorded_environment_reads_the_bundle() -> None:
    bundle = _bundle()

    assert (
        TRAIN_TRANSFORMER._recorded_environment(bundle, "dependency_versions")
        == RECORDED_DEPENDENCIES
    )
    assert TRAIN_TRANSFORMER._recorded_environment(bundle, "python_version") == RECORDED_PYTHON


def test_a_missing_environment_field_is_refused() -> None:
    with pytest.raises(ArtifactError, match="python_version"):
        TRAIN_TRANSFORMER._recorded_environment(_bundle(python_version=None), "python_version")


def test_main_does_not_remeasure_runtime_on_the_reuse_path() -> None:
    """Pin the call site, not just the helper.

    A helper that reads the bundle is worthless if `main` keeps calling
    `runtime_facts` on the reuse branch, so this asserts the branch's own source.
    """

    import inspect

    source = inspect.getsource(TRAIN_TRANSFORMER.main)
    reuse_branch = source.split("if destination.exists():", 1)[1].split("else:", 1)[0]

    assert "_reused_runtime(bundle)" in reuse_branch
    assert "runtime_facts" not in reuse_branch
