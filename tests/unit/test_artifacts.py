"""Contract tests for immutable, checksum-verified artifact bundles.

These tests use a trivial text payload rather than a fitted estimator: the
bundle contract is about identity, completeness, immutability, and checksum
verification, none of which depend on what the payload contains.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from intentguard.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    CONFIG_FILENAME,
    LABELS_FILENAME,
    MANIFEST_FILENAME,
    PROVENANCE_FILENAME,
    REQUIRED_PROVENANCE_FIELDS,
    ArtifactBundle,
    ArtifactError,
    artifact_directory,
    canonical_hash,
    compute_run_id,
    dependency_versions,
    file_hash,
    label_map_hash,
    load_artifact,
    save_artifact,
)

ARTIFACT_NAME = "stub-baseline"
DATASET_REVISION = "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
LABEL_NAMES = ("alpha", "beta", "gamma")
PAYLOAD_FILENAME = "model.stub"
CONFIG: dict[str, object] = {"regularization_c": 1.0, "solver": "lbfgs"}


def _write_payload(directory: Path) -> None:
    (directory / PAYLOAD_FILENAME).write_text("stub payload\n", encoding="utf-8")


def _provenance(run_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "artifact_name": ARTIFACT_NAME,
        "created_at": "2026-01-01T00:00:00+00:00",
        "dataset_id": "PolyAI/banking77",
        "dataset_revision": DATASET_REVISION,
        "dependency_versions": {"scikit-learn": "1.5.0"},
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
    run_id: str | None = None,
    config: Mapping[str, object] | None = None,
    label_names: Sequence[str] = LABEL_NAMES,
    provenance: Mapping[str, object] | None = None,
    write_payload: Callable[[Path], None] = _write_payload,
) -> ArtifactBundle:
    resolved_config = CONFIG if config is None else config
    resolved_run_id = run_id or compute_run_id(ARTIFACT_NAME, DATASET_REVISION, resolved_config)
    return save_artifact(
        artifact_root=root,
        artifact_name=ARTIFACT_NAME,
        run_id=resolved_run_id,
        config=resolved_config,
        label_names=label_names,
        provenance=(_provenance(resolved_run_id) if provenance is None else provenance),
        write_payload=write_payload,
    )


def _bundle_directory(root: Path, config: Mapping[str, object] | None = None) -> Path:
    resolved = CONFIG if config is None else config
    return artifact_directory(
        root, ARTIFACT_NAME, compute_run_id(ARTIFACT_NAME, DATASET_REVISION, resolved)
    )


def test_run_id_is_content_derived_and_reproducible() -> None:
    first = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    second = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, dict(reversed(list(CONFIG.items()))))
    assert first == second
    assert first.startswith(f"{ARTIFACT_NAME}-{DATASET_REVISION[:12]}-")


def test_run_id_changes_with_configuration() -> None:
    changed = dict(CONFIG) | {"regularization_c": 2.0}
    assert compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG) != compute_run_id(
        ARTIFACT_NAME, DATASET_REVISION, changed
    )


def test_run_id_changes_with_dataset_revision() -> None:
    assert compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG) != compute_run_id(
        ARTIFACT_NAME, "0" * 40, CONFIG
    )


@pytest.mark.parametrize(
    ("name", "revision"), [("", DATASET_REVISION), (ARTIFACT_NAME, "")]
)
def test_run_id_rejects_empty_identity(name: str, revision: str) -> None:
    with pytest.raises(ArtifactError, match="must not be empty"):
        compute_run_id(name, revision, CONFIG)


def test_canonical_hash_ignores_key_order() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_dependency_versions_records_installed_packages() -> None:
    versions = dependency_versions(["scikit-learn", "numpy"])
    assert set(versions) == {"scikit-learn", "numpy"}
    assert all(value for value in versions.values())


def test_dependency_versions_rejects_absent_package() -> None:
    with pytest.raises(ArtifactError, match="not installed"):
        dependency_versions(["intentguard-package-that-does-not-exist"])


def test_save_writes_the_specified_bundle_layout(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    directory = _bundle_directory(tmp_path)

    assert bundle.directory == directory
    for name in (CONFIG_FILENAME, LABELS_FILENAME, PROVENANCE_FILENAME, MANIFEST_FILENAME):
        assert (directory / name).is_file()
    assert (directory / PAYLOAD_FILENAME).is_file()
    assert bundle.payload_files == (PAYLOAD_FILENAME,)


def test_manifest_records_a_checksum_for_every_file(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    manifest = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))

    assert manifest["schema_version"] == ARTIFACT_SCHEMA_VERSION
    assert manifest["run_id"] == compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    assert set(manifest["files"]) == {
        CONFIG_FILENAME,
        LABELS_FILENAME,
        PROVENANCE_FILENAME,
        PAYLOAD_FILENAME,
    }
    for name, entry in manifest["files"].items():
        assert entry["sha256"] == file_hash(directory / name)
        assert entry["bytes"] == (directory / name).stat().st_size


def test_saved_bundle_records_configuration_labels_and_provenance(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    assert bundle.config == CONFIG
    assert bundle.label_names == LABEL_NAMES
    provenance = bundle.provenance
    for field in REQUIRED_PROVENANCE_FIELDS:
        assert provenance[field] is not None
    assert provenance["dataset_revision"] == DATASET_REVISION
    fingerprints = provenance["split_fingerprints"]
    assert isinstance(fingerprints, dict)
    assert set(fingerprints) == {"train", "validation", "test"}


def test_reload_returns_identical_metadata(tmp_path: Path) -> None:
    saved = _save(tmp_path)
    reloaded = load_artifact(_bundle_directory(tmp_path))
    assert reloaded == saved


def test_saving_refuses_to_overwrite_a_completed_bundle(tmp_path: Path) -> None:
    _save(tmp_path)
    with pytest.raises(ArtifactError, match="already exists and is immutable"):
        _save(tmp_path)


def test_refused_overwrite_leaves_the_original_bundle_intact(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    before = file_hash(directory / PAYLOAD_FILENAME)

    def _different_payload(staging: Path) -> None:
        (staging / PAYLOAD_FILENAME).write_text("replacement payload\n", encoding="utf-8")

    with pytest.raises(ArtifactError):
        _save(tmp_path, write_payload=_different_payload)

    assert file_hash(directory / PAYLOAD_FILENAME) == before
    assert load_artifact(directory).payload_files == (PAYLOAD_FILENAME,)


@pytest.mark.parametrize("field", REQUIRED_PROVENANCE_FIELDS)
def test_saving_refuses_missing_provenance_field(tmp_path: Path, field: str) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    provenance = _provenance(run_id)
    del provenance[field]
    with pytest.raises(ArtifactError, match="missing required fields"):
        _save(tmp_path, provenance=provenance)


def test_saving_refuses_incomplete_split_fingerprints(tmp_path: Path) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    provenance = _provenance(run_id, split_fingerprints={"train": "a" * 64})
    with pytest.raises(ArtifactError, match="missing split fingerprints"):
        _save(tmp_path, provenance=provenance)


def test_saving_refuses_empty_dependency_versions(tmp_path: Path) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    provenance = _provenance(run_id, dependency_versions={})
    with pytest.raises(ArtifactError, match="dependency_versions"):
        _save(tmp_path, provenance=provenance)


def test_saving_refuses_mismatched_label_map_hash(tmp_path: Path) -> None:
    run_id = compute_run_id(ARTIFACT_NAME, DATASET_REVISION, CONFIG)
    provenance = _provenance(run_id, label_map_hash="0" * 64)
    with pytest.raises(ArtifactError, match="label_map_hash"):
        _save(tmp_path, provenance=provenance)


def test_saving_refuses_mismatched_run_id(tmp_path: Path) -> None:
    provenance = _provenance("some-other-run-id")
    with pytest.raises(ArtifactError, match="run_id does not match"):
        _save(tmp_path, provenance=provenance)


@pytest.mark.parametrize(
    ("label_names", "expected"),
    [
        ((), "must not be empty"),
        (("alpha", "alpha"), "duplicate names"),
        (("alpha", ""), "empty name"),
    ],
)
def test_saving_refuses_an_invalid_label_map(
    tmp_path: Path, label_names: tuple[str, ...], expected: str
) -> None:
    with pytest.raises(ArtifactError, match=expected):
        _save(tmp_path, label_names=label_names)


def test_saving_refuses_a_bundle_without_a_payload(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="no model payload"):
        _save(tmp_path, write_payload=lambda _: None)


def test_a_failed_save_publishes_nothing(tmp_path: Path) -> None:
    def _failing_payload(_: Path) -> None:
        raise RuntimeError("payload write failed")

    with pytest.raises(RuntimeError, match="payload write failed"):
        _save(tmp_path, write_payload=_failing_payload)

    assert not _bundle_directory(tmp_path).exists()
    assert list((tmp_path / ARTIFACT_NAME).iterdir()) == []


def test_load_detects_a_payload_checksum_mismatch(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / PAYLOAD_FILENAME).write_text("tampered payload\n", encoding="utf-8")

    with pytest.raises(ArtifactError, match=f"checksum mismatch for {PAYLOAD_FILENAME}"):
        load_artifact(directory)


def test_load_detects_a_metadata_checksum_mismatch(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / CONFIG_FILENAME).write_text('{"regularization_c": 99.0}\n', encoding="utf-8")

    with pytest.raises(ArtifactError, match=f"checksum mismatch for {CONFIG_FILENAME}"):
        load_artifact(directory)


def test_load_detects_a_deleted_manifested_file(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / PAYLOAD_FILENAME).unlink()

    with pytest.raises(ArtifactError, match="missing manifested files"):
        load_artifact(directory)


def test_load_detects_an_unmanifested_extra_file(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / "smuggled.bin").write_text("extra\n", encoding="utf-8")

    with pytest.raises(ArtifactError, match="unmanifested files"):
        load_artifact(directory)


def test_load_rejects_an_absent_directory(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="does not exist"):
        load_artifact(tmp_path / "absent")


def test_load_rejects_a_missing_manifest(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / MANIFEST_FILENAME).unlink()

    with pytest.raises(ArtifactError, match=f"missing {MANIFEST_FILENAME}"):
        load_artifact(directory)


def test_load_rejects_unreadable_json(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    (directory / MANIFEST_FILENAME).write_text("{not json", encoding="utf-8")

    with pytest.raises(ArtifactError, match=f"unreadable {MANIFEST_FILENAME}"):
        load_artifact(directory)


def test_load_rejects_an_unknown_schema_version(tmp_path: Path) -> None:
    _save(tmp_path)
    directory = _bundle_directory(tmp_path)
    manifest = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["schema_version"] = ARTIFACT_SCHEMA_VERSION + 1
    (directory / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ArtifactError, match="schema version"):
        load_artifact(directory)


def test_bundle_path_returns_verified_files(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    assert bundle.path(PAYLOAD_FILENAME).is_file()
    with pytest.raises(ArtifactError, match="has no file"):
        bundle.path("absent.bin")


def test_two_configurations_coexist_as_separate_bundles(tmp_path: Path) -> None:
    other = dict(CONFIG) | {"regularization_c": 2.0}
    _save(tmp_path)
    _save(tmp_path, config=other)

    assert _bundle_directory(tmp_path).is_dir()
    assert _bundle_directory(tmp_path, other).is_dir()
    assert len(list((tmp_path / ARTIFACT_NAME).iterdir())) == 2
