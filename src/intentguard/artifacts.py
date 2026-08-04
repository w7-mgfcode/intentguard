"""Immutable, checksum-verified artifact bundles.

The bundle layout follows `ML_SYSTEM_DESIGN.md`: `artifacts/<name>/<run_id>/`
holding `config.json`, `labels.json`, `provenance.json`, `manifest.json`, and one
or more payload files or directories written by the caller. A transformer bundle
adds `threshold.json` and `validation_metrics.json`, and its payload is the
`model/` and `tokenizer/` subdirectories; both extra files are optional so the
baseline bundle, which has neither, still loads under the same schema.

Three properties matter and are enforced here rather than by convention:

* the `run_id` is derived from content, never from wall-clock time, so an
  identical dataset revision and configuration always name the same bundle;
* a bundle becomes visible only once it is complete, because it is staged in a
  sibling directory and renamed into place atomically;
* a completed bundle is never overwritten, and its files are re-hashed on load.

This module deliberately knows nothing about estimators. It never imports a
model framework, so loading a bundle cannot fit or train anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import mkdtemp
from typing import Final, cast

ARTIFACT_SCHEMA_VERSION: Final = 1
MANIFEST_FILENAME: Final = "manifest.json"
CONFIG_FILENAME: Final = "config.json"
LABELS_FILENAME: Final = "labels.json"
PROVENANCE_FILENAME: Final = "provenance.json"
THRESHOLD_FILENAME: Final = "threshold.json"
VALIDATION_METRICS_FILENAME: Final = "validation_metrics.json"
REQUIRED_METADATA_FILENAMES: Final = (CONFIG_FILENAME, LABELS_FILENAME, PROVENANCE_FILENAME)
REQUIRED_THRESHOLD_FIELDS: Final = (
    "accepted_accuracy",
    "coverage",
    "minimum_coverage",
    "rule",
    "rule_version",
    "selective_risk",
    "source",
    "threshold",
    "validation_example_count",
)
THRESHOLD_SOURCE: Final = "validation"
REQUIRED_PROVENANCE_FIELDS: Final = (
    "artifact_name",
    "created_at",
    "dataset_id",
    "dataset_revision",
    "dependency_versions",
    "label_map_hash",
    "run_id",
    "seed",
    "split_fingerprints",
)
REQUIRED_SPLIT_FINGERPRINTS: Final = ("train", "validation", "test")
_READ_CHUNK_BYTES: Final = 1 << 20


class ArtifactError(ValueError):
    """Raised when an artifact bundle violates the immutability contract."""


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    """A verified bundle: metadata plus the directory holding its payload."""

    artifact_name: str
    run_id: str
    directory: Path
    config: dict[str, object]
    label_names: tuple[str, ...]
    provenance: dict[str, object]
    payload_files: tuple[str, ...]
    threshold: dict[str, object] | None = None
    validation_metrics: dict[str, object] | None = None

    def path(self, relative_name: str) -> Path:
        """Return the verified path of one payload or metadata file."""

        candidate = self.directory / relative_name
        if not candidate.is_file():
            raise ArtifactError(f"Bundle {self.run_id} has no file {relative_name}")
        return candidate

    def directory_path(self, relative_name: str) -> Path:
        """Return the verified path of one payload subdirectory.

        A transformer payload is a directory of weights and tokenizer files, so a
        caller that hands it to `from_pretrained` needs the directory rather than a
        single file. Every file inside it was checksum-verified on load.
        """

        candidate = self.directory / relative_name
        if not candidate.is_dir():
            raise ArtifactError(f"Bundle {self.run_id} has no directory {relative_name}")
        return candidate

    def selected_threshold(self) -> float:
        """Return the persisted abstention threshold, refusing a bundle without one.

        Serving must never invent a default. A bundle with no `threshold.json`
        cannot answer the accept/abstain question at all, so this raises rather
        than falling back to a value nobody selected.
        """

        if self.threshold is None:
            raise ArtifactError(f"Bundle {self.run_id} carries no selected threshold")
        value = self.threshold.get("threshold")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ArtifactError(f"Bundle {self.run_id} has a non-numeric threshold")
        return float(value)


def canonical_hash(payload: object) -> str:
    """Hash a JSON-serialisable payload deterministically, independent of key order."""

    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    """Hash a file's bytes with SHA-256, streaming so payload size does not matter."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_READ_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def label_map_hash(label_names: Sequence[str]) -> str:
    """Hash the ordered label map, which fixes the prediction column order."""

    return canonical_hash(list(label_names))


def dependency_versions(package_names: Sequence[str]) -> dict[str, str]:
    """Record installed versions of the packages an artifact's behavior depends on."""

    versions: dict[str, str] = {}
    for name in package_names:
        try:
            versions[name] = version(name)
        except PackageNotFoundError as error:  # pragma: no cover - environment defect
            raise ArtifactError(f"Required dependency is not installed: {name}") from error
    return versions


def compute_run_id(artifact_name: str, dataset_revision: str, config: Mapping[str, object]) -> str:
    """Derive a reproducible run identifier from the dataset revision and configuration.

    `ARCHITECTURE.md` describes a timestamped directory, but a wall-clock
    identifier makes two identical runs produce two different bundles, which
    contradicts the determinism requirement and would make the refuse-overwrite
    guarantee untestable. The timestamp is recorded inside `provenance.json`
    instead, where it cannot poison the identity.
    """

    if not artifact_name:
        raise ArtifactError("Artifact name must not be empty")
    if not dataset_revision:
        raise ArtifactError("Dataset revision must not be empty")
    return f"{artifact_name}-{dataset_revision[:12]}-{canonical_hash(dict(config))[:12]}"


def artifact_directory(artifact_root: Path, artifact_name: str, run_id: str) -> Path:
    """Return the bundle directory for one run without creating it."""

    if not artifact_name or not run_id:
        raise ArtifactError("Artifact name and run ID must not be empty")
    return artifact_root / artifact_name / run_id


def _validate_provenance(
    provenance: Mapping[str, object],
    *,
    artifact_name: str,
    run_id: str,
    label_names: Sequence[str],
) -> None:
    missing = [field for field in REQUIRED_PROVENANCE_FIELDS if provenance.get(field) is None]
    if missing:
        raise ArtifactError(f"Provenance is missing required fields: {sorted(missing)}")
    if provenance["artifact_name"] != artifact_name:
        raise ArtifactError("Provenance artifact_name does not match the bundle being saved")
    if provenance["run_id"] != run_id:
        raise ArtifactError("Provenance run_id does not match the bundle being saved")
    if provenance["label_map_hash"] != label_map_hash(label_names):
        raise ArtifactError("Provenance label_map_hash does not match the saved label map")

    fingerprints = provenance["split_fingerprints"]
    if not isinstance(fingerprints, Mapping):
        raise ArtifactError("Provenance split_fingerprints must be a mapping")
    absent = [name for name in REQUIRED_SPLIT_FINGERPRINTS if not fingerprints.get(name)]
    if absent:
        raise ArtifactError(f"Provenance is missing split fingerprints: {sorted(absent)}")

    versions = provenance["dependency_versions"]
    if not isinstance(versions, Mapping) or not versions:
        raise ArtifactError("Provenance dependency_versions must be a non-empty mapping")


def _validate_threshold(threshold: Mapping[str, object]) -> None:
    """Reject a threshold record that serving could not safely act on.

    The `source` check is the leakage control at the artifact boundary: a bundle
    whose threshold was not selected from validation data is refused here, so a
    test-selected threshold cannot be published even if some future caller
    computed one.
    """

    missing = [field for field in REQUIRED_THRESHOLD_FIELDS if threshold.get(field) is None]
    if missing:
        raise ArtifactError(f"Threshold record is missing required fields: {sorted(missing)}")
    if threshold["source"] != THRESHOLD_SOURCE:
        raise ArtifactError(
            f"Threshold source must be {THRESHOLD_SOURCE!r}, not {threshold['source']!r}"
        )

    value = threshold["threshold"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactError("Threshold value must be a real number")
    if not 0.0 <= float(value) <= 1.0:
        raise ArtifactError(f"Threshold value is outside [0, 1]: {value}")

    coverage = threshold["coverage"]
    if isinstance(coverage, bool) or not isinstance(coverage, (int, float)):
        raise ArtifactError("Threshold coverage must be a real number")

    minimum = threshold["minimum_coverage"]
    if isinstance(minimum, bool) or not isinstance(minimum, (int, float)):
        raise ArtifactError("Threshold minimum_coverage must be a real number")
    if float(coverage) < float(minimum):
        raise ArtifactError(
            f"Threshold coverage {coverage} is below its own minimum {minimum}"
        )

    count = threshold["validation_example_count"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ArtifactError("Threshold validation_example_count must be a positive integer")


def _write_json(path: Path, payload: object) -> None:
    document = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(document, encoding="utf-8")


def _relative_files(directory: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            entry.relative_to(directory).as_posix()
            for entry in directory.rglob("*")
            if entry.is_file()
        )
    )


def save_artifact(
    *,
    artifact_root: Path,
    artifact_name: str,
    run_id: str,
    config: Mapping[str, object],
    label_names: Sequence[str],
    provenance: Mapping[str, object],
    write_payload: Callable[[Path], None],
    threshold: Mapping[str, object] | None = None,
    validation_metrics: Mapping[str, object] | None = None,
) -> ArtifactBundle:
    """Stage a complete bundle and publish it atomically, refusing to overwrite.

    `write_payload` receives the staging directory and writes the model payload
    into it, either as files or as subdirectories. Nothing is visible at the
    destination until every metadata file, the payload, and the checksum manifest
    exist, so an interrupted save leaves no half-written bundle behind.

    `threshold` and `validation_metrics` are optional because the E03 baseline
    bundle has neither. When a threshold is supplied it is validated before the
    bundle is published, so an unusable threshold fails the save rather than
    reaching serving.
    """

    if not label_names:
        raise ArtifactError("Artifact label map must not be empty")
    if len(set(label_names)) != len(label_names):
        raise ArtifactError("Artifact label map must not contain duplicate names")
    if any(not name for name in label_names):
        raise ArtifactError("Artifact label map must not contain an empty name")

    _validate_provenance(
        provenance, artifact_name=artifact_name, run_id=run_id, label_names=label_names
    )
    if threshold is not None:
        _validate_threshold(threshold)

    destination = artifact_directory(artifact_root, artifact_name, run_id)
    if destination.exists():
        raise ArtifactError(
            f"Artifact {artifact_name}/{run_id} already exists and is immutable: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(mkdtemp(dir=destination.parent, prefix=f".{run_id}.", suffix=".staging"))
    try:
        _write_json(staging / CONFIG_FILENAME, dict(config))
        _write_json(
            staging / LABELS_FILENAME,
            {"label_count": len(label_names), "label_names": list(label_names)},
        )
        _write_json(staging / PROVENANCE_FILENAME, dict(provenance))
        if threshold is not None:
            _write_json(staging / THRESHOLD_FILENAME, dict(threshold))
        if validation_metrics is not None:
            _write_json(staging / VALIDATION_METRICS_FILENAME, dict(validation_metrics))
        write_payload(staging)

        written = _relative_files(staging)
        absent = [name for name in REQUIRED_METADATA_FILENAMES if name not in written]
        if absent:
            raise ArtifactError(f"Staged bundle is missing metadata files: {sorted(absent)}")
        metadata_written = set(REQUIRED_METADATA_FILENAMES)
        if threshold is not None:
            metadata_written.add(THRESHOLD_FILENAME)
        if validation_metrics is not None:
            metadata_written.add(VALIDATION_METRICS_FILENAME)
        payload_files = tuple(name for name in written if name not in metadata_written)
        if not payload_files:
            raise ArtifactError("Staged bundle contains no model payload")

        _write_json(
            staging / MANIFEST_FILENAME,
            {
                "artifact_name": artifact_name,
                "files": {
                    name: {
                        "bytes": (staging / name).stat().st_size,
                        "sha256": file_hash(staging / name),
                    }
                    for name in written
                },
                "payload_files": list(payload_files),
                "run_id": run_id,
                "schema_version": ARTIFACT_SCHEMA_VERSION,
            },
        )

        try:
            os.rename(staging, destination)
        except OSError as error:
            raise ArtifactError(
                f"Artifact {artifact_name}/{run_id} could not be published atomically: {error}"
            ) from error
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return load_artifact(destination)


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ArtifactError(f"Artifact bundle is missing {path.name}: {path}")
    try:
        with path.open("rb") as stream:
            document = json.load(stream)
    except json.JSONDecodeError as error:
        raise ArtifactError(f"Artifact bundle has unreadable {path.name}: {error}") from error
    if not isinstance(document, dict):
        raise ArtifactError(f"Artifact bundle has a non-object {path.name}")
    return cast(dict[str, object], document)


def load_artifact(directory: Path) -> ArtifactBundle:
    """Verify every checksum and return the bundle metadata without fitting anything.

    Loading is inspection only: this function reads JSON and hashes bytes. It
    never constructs an estimator, so a reloaded artifact cannot be silently
    re-trained instead of restored.
    """

    if not directory.is_dir():
        raise ArtifactError(f"Artifact bundle directory does not exist: {directory}")

    manifest = _read_json(directory / MANIFEST_FILENAME)
    if manifest.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactError(
            f"Artifact manifest schema version is not {ARTIFACT_SCHEMA_VERSION}: {directory}"
        )

    artifact_name = manifest.get("artifact_name")
    run_id = manifest.get("run_id")
    files = manifest.get("files")
    payload_files = manifest.get("payload_files")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise ArtifactError(f"Artifact manifest has no artifact_name: {directory}")
    if not isinstance(run_id, str) or not run_id:
        raise ArtifactError(f"Artifact manifest has no run_id: {directory}")
    if not isinstance(files, dict) or not files:
        raise ArtifactError(f"Artifact manifest lists no files: {directory}")
    if not isinstance(payload_files, list) or not payload_files:
        raise ArtifactError(f"Artifact manifest lists no payload files: {directory}")
    for entry in payload_files:
        # A malformed entry must fail here as an ArtifactError rather than escaping
        # later as an unrelated TypeError from path joining.
        if not isinstance(entry, str) or not entry:
            raise ArtifactError(
                f"Artifact manifest payload file entry is not a name: {entry!r}"
            )
        if entry not in files:
            raise ArtifactError(
                f"Artifact manifest payload file is not manifested: {entry!r}"
            )

    present = set(_relative_files(directory)) - {MANIFEST_FILENAME}
    listed = set(files)
    if missing := sorted(listed - present):
        raise ArtifactError(f"Artifact bundle is missing manifested files: {missing}")
    if unexpected := sorted(present - listed):
        raise ArtifactError(f"Artifact bundle contains unmanifested files: {unexpected}")

    for name in sorted(listed):
        entry = files[name]
        if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str):
            raise ArtifactError(f"Artifact manifest entry for {name} has no checksum")
        if file_hash(directory / name) != entry["sha256"]:
            raise ArtifactError(f"Artifact bundle checksum mismatch for {name}: {directory}")

    labels = _read_json(directory / LABELS_FILENAME)
    label_names = labels.get("label_names")
    if (
        not isinstance(label_names, list)
        or not label_names
        or not all(isinstance(name, str) and name for name in label_names)
    ):
        raise ArtifactError(f"Artifact bundle has an invalid label map: {directory}")

    provenance = _read_json(directory / PROVENANCE_FILENAME)
    resolved = tuple(cast(list[str], label_names))
    _validate_provenance(
        provenance, artifact_name=artifact_name, run_id=run_id, label_names=resolved
    )

    # Both files are optional so the E03 baseline bundle still loads. When a
    # threshold is present it is re-validated on every load, not only at save
    # time, because the bundle on disk is what serving will actually act on.
    threshold: dict[str, object] | None = None
    if (directory / THRESHOLD_FILENAME).is_file():
        threshold = _read_json(directory / THRESHOLD_FILENAME)
        _validate_threshold(threshold)

    validation_metrics: dict[str, object] | None = None
    if (directory / VALIDATION_METRICS_FILENAME).is_file():
        validation_metrics = _read_json(directory / VALIDATION_METRICS_FILENAME)

    return ArtifactBundle(
        artifact_name=artifact_name,
        run_id=run_id,
        directory=directory,
        config=_read_json(directory / CONFIG_FILENAME),
        label_names=resolved,
        provenance=provenance,
        payload_files=tuple(cast(list[str], payload_files)),
        threshold=threshold,
        validation_metrics=validation_metrics,
    )
