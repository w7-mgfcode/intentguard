"""The transformer run identity must change whenever the bundle would change.

`make train` reuses an existing bundle when the run ID already exists on disk,
and the refuse-to-overwrite guard means no save is attempted. So any input that
changes what the bundle contains but not the ID would leave a stale artifact in
place while this run reported success — including a changed coverage floor, which
does not alter the fitted weights but does alter the threshold serving acts on.

This mirrors `tests/unit/test_run_identity.py` for the baseline. Nothing here
loads a model: importing the script only defines its functions, because `main` is
guarded.
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


class _StubPrepared:
    """Only `provenance["split_fingerprints"]` is read by the identity payload."""

    def __init__(self, fingerprints: dict[str, str]) -> None:
        self.provenance: dict[str, Any] = {"split_fingerprints": dict(fingerprints)}


def _config() -> FoundationConfig:
    return load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")


def _run_id(config: FoundationConfig, fingerprints: dict[str, str] | None = None) -> str:
    prepared = _StubPrepared(fingerprints or SPLIT_FINGERPRINTS)
    return compute_run_id(
        TRAIN_TRANSFORMER.ARTIFACT_NAME,
        config.dataset_revision,
        TRAIN_TRANSFORMER._run_identity_payload(config, prepared),
    )


def test_identical_configuration_yields_a_stable_run_id() -> None:
    assert _run_id(_config()) == _run_id(_config())


def test_the_transformer_run_id_is_not_the_baseline_run_id() -> None:
    config = _config()
    baseline_style = compute_run_id(
        "intentguard-baseline",
        config.dataset_revision,
        TRAIN_TRANSFORMER._run_identity_payload(config, _StubPrepared(SPLIT_FINGERPRINTS)),
    )

    assert _run_id(config) != baseline_style
    assert _run_id(config).startswith("intentguard-distilbert-")


def test_a_changed_seed_changes_the_run_id() -> None:
    config = _config()
    assert _run_id(config) != _run_id(replace(config, seed=config.seed + 1))


def test_a_changed_base_model_revision_changes_the_run_id() -> None:
    config = _config()
    # The weights start from this checkpoint, so a different pin is a different
    # model even with every hyperparameter unchanged.
    assert _run_id(config) != _run_id(replace(config, base_model_revision="f" * 40))


def test_a_changed_base_model_id_changes_the_run_id() -> None:
    config = _config()
    assert _run_id(config) != _run_id(replace(config, base_model_id="other/model"))


def test_a_changed_dataset_revision_changes_the_run_id() -> None:
    config = _config()
    assert _run_id(config) != _run_id(replace(config, dataset_revision="f" * 40))


def test_a_changed_validation_fraction_changes_the_run_id() -> None:
    config = _config()
    other = replace(config, validation_fraction=config.validation_fraction + 0.05)
    assert _run_id(config) != _run_id(other)


def test_changed_split_fingerprints_change_the_run_id() -> None:
    config = _config()
    moved = dict(SPLIT_FINGERPRINTS) | {"train": "d" * 64}
    assert _run_id(config) != _run_id(config, moved)


def test_every_training_hyperparameter_changes_the_run_id() -> None:
    config = _config()
    changed: dict[str, Any] = {
        "max_sequence_length": 128,
        "epochs": 3,
        "train_batch_size": 8,
        "eval_batch_size": 16,
        "learning_rate": 3e-5,
        "weight_decay": 0.0,
        "warmup_ratio": 0.0,
        "max_grad_norm": 0.5,
    }

    for name, value in changed.items():
        other = replace(config, training=replace(config.training, **{name: value}))
        assert _run_id(config) != _run_id(other), name


def test_a_changed_coverage_floor_changes_the_run_id() -> None:
    config = _config()
    # The floor does not change the weights, but it changes the threshold written
    # into the bundle, which is what serving acts on.
    other = replace(config, threshold=replace(config.threshold, minimum_coverage=0.5))

    assert _run_id(config) != _run_id(other)


def test_run_identity_covers_every_field_that_reaches_the_bundle() -> None:
    """A new bundle-affecting field must be added to the identity deliberately."""

    payload = TRAIN_TRANSFORMER._run_identity_payload(
        _config(), _StubPrepared(SPLIT_FINGERPRINTS)
    )

    assert set(payload) == {
        "base_model_id",
        "base_model_revision",
        "seed",
        "split_fingerprints",
        "threshold",
        "training",
        "validation_fraction",
    }
    assert set(payload["training"]) == {
        "epochs",
        "eval_batch_size",
        "learning_rate",
        "max_grad_norm",
        "max_sequence_length",
        "selection_metric",
        "threshold_source",
        "train_batch_size",
        "warmup_ratio",
        "weight_decay",
    }
    assert set(payload["threshold"]) == {"minimum_coverage", "objective"}


def test_the_identity_payload_carries_no_test_derived_quantity() -> None:
    # The train split fingerprint identifies the data trained on; the test
    # fingerprint is present only because the dataset provenance is recorded as a
    # whole. No test label, count, or metric may appear anywhere in the identity.
    payload = TRAIN_TRANSFORMER._run_identity_payload(
        _config(), _StubPrepared(SPLIT_FINGERPRINTS)
    )

    assert TRAIN_TRANSFORMER._training_config_payload(
        _config().training
    )["threshold_source"] == "validation"
    assert set(payload["split_fingerprints"]) == {"train", "validation", "test"}
