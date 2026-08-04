"""Contract tests for the transformer bundle extensions (AC-006, S04.3).

A transformer bundle differs from the baseline bundle in three ways: its payload
is nested directories rather than one file, it carries `threshold.json`, and it
carries `validation_metrics.json`. Each is tested here without loading a real
model — the bundle contract is about identity, completeness, checksum coverage,
and threshold usability, none of which depend on the weights being genuine.

The baseline bundle has neither extra file, so every test that adds one is paired
with a check that omitting it still loads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from intentguard.artifacts import (
    MANIFEST_FILENAME,
    REQUIRED_THRESHOLD_FIELDS,
    THRESHOLD_FILENAME,
    VALIDATION_METRICS_FILENAME,
    ArtifactBundle,
    ArtifactError,
    artifact_directory,
    compute_run_id,
    file_hash,
    label_map_hash,
    load_artifact,
    save_artifact,
)

ARTIFACT_NAME = "stub-distilbert"
DATASET_REVISION = "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
LABEL_NAMES = ("alpha", "beta", "gamma")
CONFIG: dict[str, object] = {"epochs": 2, "learning_rate": 2e-5}

MODEL_DIRECTORY = "model"
TOKENIZER_DIRECTORY = "tokenizer"


def _write_nested_payload(staging: Path) -> None:
    """Write a payload shaped like a real transformer save: two subdirectories."""

    model = staging / MODEL_DIRECTORY
    model.mkdir()
    (model / "config.json").write_text('{"model_type": "distilbert"}\n', encoding="utf-8")
    (model / "model.safetensors").write_bytes(b"stub weights\n")

    tokenizer = staging / TOKENIZER_DIRECTORY
    tokenizer.mkdir()
    (tokenizer / "tokenizer_config.json").write_text("{}\n", encoding="utf-8")
    (tokenizer / "vocab.txt").write_text("[PAD]\n[UNK]\n", encoding="utf-8")


def _write_single_file_payload(staging: Path) -> None:
    """Write a baseline-shaped payload: one file, no subdirectories."""

    (staging / "model.joblib").write_bytes(b"stub\n")


def _threshold(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "threshold": 0.6,
        "rule": "min_selective_risk_at_min_coverage",
        "rule_version": 1,
        "source": "validation",
        "minimum_coverage": 0.70,
        "validation_example_count": 1501,
        "coverage": 0.8,
        "accepted_count": 1201,
        "accepted_accuracy": 0.875,
        "selective_risk": 0.125,
        "candidate_count": 1200,
    }
    payload.update(overrides)
    return payload


def _validation_metrics() -> dict[str, Any]:
    return {
        "metric_version": 1,
        "example_count": 1501,
        "accuracy": 0.9,
        "macro_f1": 0.89,
        "weighted_f1": 0.9,
        "per_class": [],
    }


def _provenance(run_id: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "artifact_name": ARTIFACT_NAME,
        "created_at": "2026-01-01T00:00:00+00:00",
        "dataset_id": "PolyAI/banking77",
        "dataset_revision": DATASET_REVISION,
        "dependency_versions": {"torch": "2.13.0+cpu", "transformers": "5.14.1"},
        "label_map_hash": label_map_hash(LABEL_NAMES),
        "run_id": run_id,
        "seed": 42,
        "split_fingerprints": {"train": "a" * 64, "validation": "b" * 64, "test": "c" * 64},
    }
    payload.update(overrides)
    return payload


def _save(
    root: Path,
    *,
    threshold: dict[str, Any] | None = None,
    validation_metrics: dict[str, Any] | None = None,
    config: dict[str, object] | None = None,
    write_payload: Any = _write_nested_payload,
) -> ArtifactBundle:
    resolved_config = CONFIG if config is None else config
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, resolved_config)
    return save_artifact(
        artifact_root=root,
        artifact_name=ARTIFACT_NAME,
        run_id=run_id,
        config=resolved_config,
        label_names=LABEL_NAMES,
        provenance=_provenance(run_id),
        write_payload=write_payload,
        threshold=_threshold() if threshold is None else threshold,
        validation_metrics=(
            _validation_metrics() if validation_metrics is None else validation_metrics
        ),
    )


def _directory(root: Path, config: dict[str, object] | None = None) -> Path:
    resolved = CONFIG if config is None else config
    return artifact_directory(
        root, ARTIFACT_NAME, compute_run_id(ARTIFACT_NAME, DATASET_REVISION, resolved)
    )


# --- Nested payload ---------------------------------------------------------


def test_nested_payload_directories_are_saved_and_reloaded(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    assert bundle.directory_path(MODEL_DIRECTORY).is_dir()
    assert bundle.directory_path(TOKENIZER_DIRECTORY).is_dir()
    assert (bundle.directory / MODEL_DIRECTORY / "model.safetensors").is_file()


def test_every_nested_payload_file_is_manifested_with_a_checksum(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest = json.loads((bundle.directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))

    expected = {
        "model/config.json",
        "model/model.safetensors",
        "tokenizer/tokenizer_config.json",
        "tokenizer/vocab.txt",
    }
    assert expected <= set(manifest["files"])
    assert expected <= set(manifest["payload_files"])
    for name in expected:
        assert manifest["files"][name]["sha256"] == file_hash(bundle.directory / name)


def test_payload_files_use_posix_relative_names(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    # Manifest keys must be portable, forward-slash relative names rather than
    # platform-specific paths, or a bundle written here would not verify elsewhere.
    assert all("\\" not in name for name in bundle.payload_files)
    assert all(not Path(name).is_absolute() for name in bundle.payload_files)


def test_tampering_with_a_nested_weight_file_is_detected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    (bundle.directory / MODEL_DIRECTORY / "model.safetensors").write_bytes(b"tampered\n")

    with pytest.raises(ArtifactError, match=r"checksum mismatch for model/model\.safetensors"):
        load_artifact(bundle.directory)


def test_a_deleted_nested_tokenizer_file_is_detected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    (bundle.directory / TOKENIZER_DIRECTORY / "vocab.txt").unlink()

    with pytest.raises(ArtifactError, match="missing manifested files"):
        load_artifact(bundle.directory)


def test_an_extra_file_smuggled_into_a_payload_directory_is_detected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    (bundle.directory / MODEL_DIRECTORY / "extra.bin").write_bytes(b"extra\n")

    with pytest.raises(ArtifactError, match="unmanifested files"):
        load_artifact(bundle.directory)


def test_requesting_a_directory_as_a_file_is_rejected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    with pytest.raises(ArtifactError, match="has no file"):
        bundle.path(MODEL_DIRECTORY)


def test_requesting_a_file_as_a_directory_is_rejected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    with pytest.raises(ArtifactError, match="has no directory"):
        bundle.directory_path("config.json")


# --- Threshold record -------------------------------------------------------


def test_the_selected_threshold_survives_a_save_and_reload(tmp_path: Path) -> None:
    saved = _save(tmp_path)
    reloaded = load_artifact(_directory(tmp_path))

    assert reloaded == saved
    assert reloaded.selected_threshold() == 0.6
    assert reloaded.threshold is not None
    assert reloaded.threshold["source"] == "validation"


def test_threshold_json_is_metadata_and_not_counted_as_payload(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    assert THRESHOLD_FILENAME not in bundle.payload_files
    assert VALIDATION_METRICS_FILENAME not in bundle.payload_files
    # Still manifested and checksum-covered, just not the model payload.
    manifest = json.loads((bundle.directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert THRESHOLD_FILENAME in manifest["files"]
    assert VALIDATION_METRICS_FILENAME in manifest["files"]


def test_a_tampered_threshold_is_detected_on_load(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    record = _threshold(threshold=0.0)
    (bundle.directory / THRESHOLD_FILENAME).write_text(json.dumps(record), encoding="utf-8")

    # Lowering the threshold to accept everything is exactly the tampering that
    # would inflate coverage, so the checksum must catch it.
    with pytest.raises(ArtifactError, match=f"checksum mismatch for {THRESHOLD_FILENAME}"):
        load_artifact(bundle.directory)


@pytest.mark.parametrize("field", REQUIRED_THRESHOLD_FIELDS)
def test_saving_refuses_an_incomplete_threshold(tmp_path: Path, field: str) -> None:
    record = _threshold()
    del record[field]

    with pytest.raises(ArtifactError, match="missing required fields"):
        _save(tmp_path, threshold=record)


def test_saving_refuses_a_threshold_not_sourced_from_validation(tmp_path: Path) -> None:
    # The leakage control at the artifact boundary: a test-selected threshold
    # cannot be published even if something upstream computed one.
    with pytest.raises(ArtifactError, match="source must be"):
        _save(tmp_path, threshold=_threshold(source="test"))


@pytest.mark.parametrize("value", [-0.1, 1.1, "0.6", True])
def test_saving_refuses_an_unusable_threshold_value(tmp_path: Path, value: object) -> None:
    with pytest.raises(ArtifactError):
        _save(tmp_path, threshold=_threshold(threshold=value))


def test_saving_refuses_a_threshold_below_its_own_minimum_coverage(tmp_path: Path) -> None:
    # An internally inconsistent record: the selection claims a 0.70 floor but
    # reports 0.50 coverage, so one of the two is wrong.
    with pytest.raises(ArtifactError, match="below its own minimum"):
        _save(tmp_path, threshold=_threshold(coverage=0.5, minimum_coverage=0.7))


def test_saving_refuses_a_coverage_outside_the_unit_interval(tmp_path: Path) -> None:
    # 1.5 coverage still satisfies `coverage >= minimum_coverage`, so the ordering
    # check cannot catch it. Coverage is a fraction of the validation set, and a
    # record claiming 150% of it is impossible however self-consistent it looks.
    with pytest.raises(ArtifactError, match="coverage is outside"):
        _save(tmp_path, threshold=_threshold(coverage=1.5, minimum_coverage=0.7))


def test_saving_refuses_a_minimum_coverage_outside_the_unit_interval(tmp_path: Path) -> None:
    # A negative floor is below any real coverage, so the ordering check passes and
    # only the range guard rejects it.
    with pytest.raises(ArtifactError, match="minimum_coverage is outside"):
        _save(tmp_path, threshold=_threshold(coverage=0.8, minimum_coverage=-0.5))


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_saving_refuses_a_non_positive_validation_example_count(
    tmp_path: Path, value: object
) -> None:
    with pytest.raises(ArtifactError, match="validation_example_count"):
        _save(tmp_path, threshold=_threshold(validation_example_count=value))


def test_a_failed_threshold_validation_publishes_nothing(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError):
        _save(tmp_path, threshold=_threshold(source="test"))

    assert not _directory(tmp_path).exists()


# --- Backward compatibility with the baseline bundle ------------------------


def test_a_bundle_without_a_threshold_still_loads(tmp_path: Path) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    saved = save_artifact(
        artifact_root=tmp_path,
        artifact_name=ARTIFACT_NAME,
        run_id=run_id,
        config=CONFIG,
        label_names=LABEL_NAMES,
        provenance=_provenance(run_id),
        write_payload=_write_single_file_payload,
    )

    assert saved.threshold is None
    assert saved.validation_metrics is None
    assert not (saved.directory / THRESHOLD_FILENAME).exists()
    assert load_artifact(saved.directory) == saved


def test_a_bundle_without_a_threshold_refuses_to_invent_one(tmp_path: Path) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    saved = save_artifact(
        artifact_root=tmp_path,
        artifact_name=ARTIFACT_NAME,
        run_id=run_id,
        config=CONFIG,
        label_names=LABEL_NAMES,
        provenance=_provenance(run_id),
        write_payload=_write_single_file_payload,
    )

    # Serving must fail loudly rather than fall back to a default nobody selected.
    with pytest.raises(ArtifactError, match="carries no selected threshold"):
        saved.selected_threshold()


def test_validation_metrics_are_optional_and_round_trip(tmp_path: Path) -> None:
    bundle = _save(tmp_path)

    assert bundle.validation_metrics == _validation_metrics()
    assert load_artifact(bundle.directory).validation_metrics == _validation_metrics()


# --- Immutability still holds for the extended layout -----------------------


def test_the_extended_bundle_refuses_to_be_overwritten(tmp_path: Path) -> None:
    _save(tmp_path)

    with pytest.raises(ArtifactError, match="already exists and is immutable"):
        _save(tmp_path)


def test_a_failed_nested_payload_write_publishes_nothing(tmp_path: Path) -> None:
    def _failing(staging: Path) -> None:
        (staging / MODEL_DIRECTORY).mkdir()
        (staging / MODEL_DIRECTORY / "partial.bin").write_bytes(b"half\n")
        raise RuntimeError("weight write failed")

    with pytest.raises(RuntimeError, match="weight write failed"):
        _save(tmp_path, write_payload=_failing)

    assert not _directory(tmp_path).exists()
    assert list((tmp_path / ARTIFACT_NAME).iterdir()) == []


def test_a_bundle_whose_payload_is_only_metadata_is_refused(tmp_path: Path) -> None:
    # threshold.json and validation_metrics.json are metadata, so a "payload" of
    # nothing but those must not count as a model.
    with pytest.raises(ArtifactError, match="no model payload"):
        _save(tmp_path, write_payload=lambda _: None)
