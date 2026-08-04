"""Train, persist, reload, and measure the TF-IDF logistic-regression baseline.

The order of operations here is the leakage control, not a convention:

1. hyperparameters are read from configuration, already frozen and validated;
2. the pipeline is fitted on the canonical train split only;
3. a validation-only sanity check runs, so nothing is inspected on test before
   the artifact is sealed;
4. the artifact is saved immutably and then **reloaded from disk**;
5. only the reloaded artifact touches the canonical test split, exactly once.

`REQUIREMENTS.md` AC-002 requires `make baseline` to write test macro-F1,
accuracy, and per-class metrics. `ARCHITECTURE.md` instead assigns test
evaluation to `make evaluate`. `REQUIREMENTS.md` outranks `ARCHITECTURE.md` in
the repository precedence order, so the test split is evaluated here — safely,
because every hyperparameter was frozen before any test read and the reloaded
artifact cannot be re-tuned.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final

import joblib  # type: ignore[import-untyped]
import numpy as np

from intentguard.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    ArtifactBundle,
    ArtifactError,
    artifact_directory,
    canonical_hash,
    compute_run_id,
    dependency_versions,
    label_map_hash,
    load_artifact,
    save_artifact,
)
from intentguard.baseline import (
    BaselineError,
    build_pipeline,
    fit_pipeline,
    labels_from_probabilities,
    predict_probabilities,
    vocabulary,
)
from intentguard.config import BaselineConfig, FoundationConfig, load_foundation_config
from intentguard.data import (
    DataContractError,
    load_pinned_dataset,
    prepare_dataset,
)
from intentguard.metrics import METRIC_VERSION, compute_classification_metrics, metrics_payload
from intentguard.schemas import CanonicalExample, PreparedDataset

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
ARTIFACT_NAME: Final = "intentguard-baseline"
MODEL_FILENAME: Final = "model.joblib"
REPORT_FILENAME: Final = "metrics.json"
REPORT_SCHEMA_VERSION: Final = 1
RELOAD_PROBABILITY_TOLERANCE: Final = 1e-12
TRACKED_DEPENDENCIES: Final = ("joblib", "numpy", "scikit-learn")


def _baseline_config_payload(config: BaselineConfig) -> dict[str, object]:
    """Render the frozen hyperparameters, which also define the run identity."""

    return {
        "class_weight": config.class_weight,
        "lowercase": config.lowercase,
        "max_features": config.max_features,
        "max_iter": config.max_iter,
        "min_df": config.min_df,
        "ngram_max": config.ngram_max,
        "ngram_min": config.ngram_min,
        "regularization_c": config.regularization_c,
        "solver": config.solver,
        "sublinear_tf": config.sublinear_tf,
    }


def _texts_and_labels(
    examples: tuple[CanonicalExample, ...],
) -> tuple[list[str], list[int]]:
    return [example.text for example in examples], [example.label_id for example in examples]


def _example_id_hash(examples: tuple[CanonicalExample, ...]) -> str:
    """Hash the evaluated example IDs, as required by the evaluation manifest."""

    return canonical_hash([example.example_id for example in examples])


def _write_json_atomically(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(document)
        temporary.replace(path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _save_baseline_artifact(
    config: FoundationConfig,
    prepared: PreparedDataset,
    run_id: str,
    pipeline: object,
) -> ArtifactBundle:
    provenance: dict[str, object] = {
        "artifact_name": ARTIFACT_NAME,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": config.dataset_id,
        "dataset_revision": config.dataset_revision,
        "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
        "derived_split_counts": prepared.provenance["derived_split_counts"],
        "label_map_hash": label_map_hash(prepared.label_names),
        "label_map_sha256": prepared.provenance["label_map_sha256"],
        "model_payload": MODEL_FILENAME,
        "python_version": platform.python_version(),
        "run_id": run_id,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "seed": config.seed,
        "split_fingerprints": prepared.provenance["split_fingerprints"],
        "trained_on_split": "train",
        "validation_selection_split": "validation",
    }

    def _write_payload(staging: Path) -> None:
        joblib.dump(pipeline, staging / MODEL_FILENAME)

    return save_artifact(
        artifact_root=config.artifact_root,
        artifact_name=ARTIFACT_NAME,
        run_id=run_id,
        config=_baseline_config_payload(config.baseline),
        label_names=prepared.label_names,
        provenance=provenance,
        write_payload=_write_payload,
    )


def _verify_reload_parity(
    bundle: ArtifactBundle,
    reference_probabilities: np.ndarray,
    texts: list[str],
    label_count: int,
) -> object:
    """Reload from disk and prove the restored model reproduces the in-memory one.

    Reload parity is checked on the validation split, before any test read, so a
    corrupt or drifted artifact fails the run rather than silently producing a
    wrong test measurement.
    """

    reloaded = joblib.load(bundle.path(MODEL_FILENAME))
    probabilities = predict_probabilities(reloaded, texts, label_count=label_count)

    if labels_from_probabilities(probabilities) != labels_from_probabilities(
        reference_probabilities
    ):
        raise ArtifactError("Reloaded baseline produced different labels than the fitted model")
    if not np.allclose(
        probabilities, reference_probabilities, atol=RELOAD_PROBABILITY_TOLERANCE, rtol=0.0
    ):
        raise ArtifactError(
            "Reloaded baseline probabilities diverged beyond the approved tolerance"
        )
    return reloaded


def main() -> None:
    """Run the complete baseline lifecycle and write one machine-readable report."""

    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
    prepared = prepare_dataset(load_pinned_dataset(config), config)
    label_count = len(prepared.label_names)

    train_texts, train_labels = _texts_and_labels(prepared.train)
    validation_texts, validation_labels = _texts_and_labels(prepared.validation)

    run_id = compute_run_id(
        ARTIFACT_NAME, config.dataset_revision, _baseline_config_payload(config.baseline)
    )
    destination = artifact_directory(config.artifact_root, ARTIFACT_NAME, run_id)
    if destination.exists():
        bundle = load_artifact(destination)
        print(
            json.dumps(
                {"reused_existing_artifact": True, "run_id": bundle.run_id}, sort_keys=True
            ),
            file=sys.stderr,
        )
    else:
        pipeline = fit_pipeline(
            build_pipeline(config.baseline, config.seed),
            train_texts,
            train_labels,
            label_count=label_count,
        )

        held_out_tokens = {
            token
            for text in validation_texts
            for token in text.lower().split()
            if token not in vocabulary(pipeline)
        }
        validation_probabilities = predict_probabilities(
            pipeline, validation_texts, label_count=label_count
        )
        validation_metrics = compute_classification_metrics(
            validation_labels,
            labels_from_probabilities(validation_probabilities),
            prepared.label_names,
        )

        bundle = _save_baseline_artifact(config, prepared, run_id, pipeline)
        _verify_reload_parity(
            bundle, validation_probabilities, validation_texts, label_count
        )
        print(
            json.dumps(
                {
                    "validation_macro_f1": validation_metrics.macro_f1,
                    "validation_only_tokens_absent_from_vocabulary": len(held_out_tokens),
                    "reload_parity": "verified",
                    "run_id": bundle.run_id,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )

    # From here on the test split is read exactly once, through the reloaded
    # artifact only. The in-memory model is deliberately not used again.
    evaluation_model = joblib.load(bundle.path(MODEL_FILENAME))
    test_texts, test_labels = _texts_and_labels(prepared.test)
    test_probabilities = predict_probabilities(
        evaluation_model, test_texts, label_count=label_count
    )
    test_metrics = compute_classification_metrics(
        test_labels, labels_from_probabilities(test_probabilities), prepared.label_names
    )

    report: dict[str, object] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "artifact_name": bundle.artifact_name,
        "run_id": bundle.run_id,
        "artifact_directory": str(bundle.directory),
        "evaluated_from": "reloaded_artifact",
        "split": "test",
        "dataset_id": config.dataset_id,
        "dataset_revision": config.dataset_revision,
        "split_fingerprints": prepared.provenance["split_fingerprints"],
        "label_map_sha256": prepared.provenance["label_map_sha256"],
        "label_map_hash": label_map_hash(prepared.label_names),
        "test_example_id_sha256": _example_id_hash(prepared.test),
        "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
        "python_version": platform.python_version(),
        "seed": config.seed,
        "baseline_config": _baseline_config_payload(config.baseline),
        "metrics": metrics_payload(test_metrics),
    }
    report_path = config.report_root / "baseline" / bundle.run_id / REPORT_FILENAME
    _write_json_atomically(report_path, report)

    print(
        json.dumps(
            {
                "accuracy": test_metrics.accuracy,
                "example_count": test_metrics.example_count,
                "macro_f1": test_metrics.macro_f1,
                "report_path": str(report_path),
                "run_id": bundle.run_id,
                "weighted_f1": test_metrics.weighted_f1,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ArtifactError, BaselineError, DataContractError, ValueError) as error:
        raise SystemExit(f"Baseline training failed: {error}") from error
