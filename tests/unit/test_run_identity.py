"""The baseline run identity must change whenever the fitted model would change.

`make baseline` reuses an existing bundle when the run ID already exists on disk,
and the refuse-to-overwrite guard means no save is attempted. So any input that
changes the model but not the ID would silently publish a report describing this
run's configuration alongside a previous run's model.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from intentguard.artifacts import compute_run_id
from intentguard.config import FoundationConfig, load_foundation_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

SPLIT_FINGERPRINTS = {
    "train": "a" * 64,
    "validation": "b" * 64,
    "test": "c" * 64,
}


def _load_train_baseline() -> ModuleType:
    """Import the orchestration script without running it; `main` is guarded."""

    script_path = REPOSITORY_ROOT / "scripts" / "train_baseline.py"
    specification = spec_from_file_location("train_baseline", script_path)
    assert specification is not None and specification.loader is not None
    module = module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


TRAIN_BASELINE = _load_train_baseline()


class _StubPrepared:
    """Only `provenance["split_fingerprints"]` is read by the identity payload."""

    def __init__(self, fingerprints: dict[str, str]) -> None:
        self.provenance: dict[str, Any] = {"split_fingerprints": dict(fingerprints)}


def _config() -> FoundationConfig:
    return load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")


def _run_id(config: FoundationConfig, fingerprints: dict[str, str] | None = None) -> str:
    prepared = _StubPrepared(fingerprints or SPLIT_FINGERPRINTS)
    return compute_run_id(
        TRAIN_BASELINE.ARTIFACT_NAME,
        config.dataset_revision,
        TRAIN_BASELINE._run_identity_payload(config, prepared),
    )


def test_identical_configuration_yields_a_stable_run_id() -> None:
    assert _run_id(_config()) == _run_id(_config())


def test_a_changed_seed_changes_the_run_id() -> None:
    config = _config()
    assert _run_id(config) != _run_id(replace(config, seed=config.seed + 1))


def test_a_changed_validation_fraction_changes_the_run_id() -> None:
    config = _config()
    other = replace(config, validation_fraction=config.validation_fraction + 0.05)
    assert _run_id(config) != _run_id(other)


def test_changed_split_fingerprints_change_the_run_id() -> None:
    config = _config()
    moved = dict(SPLIT_FINGERPRINTS) | {"train": "d" * 64}
    assert _run_id(config) != _run_id(config, moved)


def test_a_changed_hyperparameter_changes_the_run_id() -> None:
    config = _config()
    other = replace(config, baseline=replace(config.baseline, regularization_c=2.0))
    assert _run_id(config) != _run_id(other)


def test_a_changed_dataset_revision_changes_the_run_id() -> None:
    config = _config()
    assert _run_id(config) != _run_id(replace(config, dataset_revision="f" * 40))


def test_run_identity_covers_every_field_that_reaches_the_model() -> None:
    """A new model-affecting field must be added to the identity deliberately."""

    payload = TRAIN_BASELINE._run_identity_payload(
        _config(), _StubPrepared(SPLIT_FINGERPRINTS)
    )

    assert set(payload) == {"baseline", "seed", "split_fingerprints", "validation_fraction"}
