"""Fine-tune DistilBERT, select the abstention threshold, and seal one bundle.

The order of operations here is the leakage control, not a convention:

1. every hyperparameter is read from frozen, validated configuration;
2. fine-tuning sees the canonical train split only;
3. the epoch to keep is chosen by validation macro-F1 only;
4. the threshold is selected from validation confidences only, through an API
   that has no parameter capable of carrying a test label;
5. the bundle is sealed immutably and then **reloaded from disk**, and the
   restored model must reproduce the same labels, probabilities, and — the part
   that actually matters for serving — the same accept/abstain decisions.

The canonical test split is never read here. `REQUIREMENTS.md` AC-004 assigns
test evaluation to `make evaluate`, so this script writes no test metrics and the
precedence conflict that applied to `make baseline` does not recur.

Everything runs on CPU. Device, thread count, and peak memory are recorded as
measured facts; `NFR-001`'s GPU clause is left unevidenced rather than inferred.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Final

import numpy as np
import torch
from transformers import PreTrainedModel, PreTrainedTokenizerBase

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
from intentguard.config import (
    FoundationConfig,
    ThresholdConfig,
    TrainingConfig,
    load_foundation_config,
)
from intentguard.data import DataContractError, load_pinned_dataset, prepare_dataset
from intentguard.metrics import (
    METRIC_VERSION,
    ClassificationMetrics,
    compute_classification_metrics,
    metrics_payload,
)
from intentguard.schemas import CanonicalExample, PreparedDataset
from intentguard.threshold import (
    CoveragePoint,
    ThresholdError,
    ThresholdSelection,
    coverage_curve,
    decide,
    select_threshold,
    selection_payload,
)
from intentguard.training import (
    TrainingError,
    build_optimizer,
    build_schedule,
    confidences_from_probabilities,
    encode,
    forward_loss,
    labels_from_probabilities,
    load_model,
    load_model_from_directory,
    load_tokenizer,
    load_tokenizer_from_directory,
    move_to_device,
    predict_probabilities,
    resolve_device,
    runtime_facts,
    runtime_payload,
    seed_training,
    total_optimisation_steps,
    train_batches,
)

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
ARTIFACT_NAME: Final = "intentguard-distilbert"
MODEL_DIRECTORY: Final = "model"
TOKENIZER_DIRECTORY: Final = "tokenizer"
REPORT_FILENAME: Final = "training.json"
REPORT_SCHEMA_VERSION: Final = 1
PROGRESS_EVERY_STEPS: Final = 50
TRACKED_DEPENDENCIES: Final = (
    "numpy",
    "safetensors",
    "scikit-learn",
    "tokenizers",
    "torch",
    "transformers",
)

# `safetensors` round-trips float32 weights byte-for-byte, so a reloaded model is
# expected to reproduce the fitted one exactly. The tolerance guards against
# kernel-level scheduling differences between two passes on the same machine, not
# against precision loss; predicted labels and decisions are compared exactly.
RELOAD_PROBABILITY_TOLERANCE: Final = 1e-9

# The selected epoch's weights are restored before the authoritative validation
# pass. Restoring the wrong state would change macro-F1, so the recomputed value
# is compared against the value that won selection.
SELECTION_METRIC_TOLERANCE: Final = 1e-9


def _log(payload: dict[str, object]) -> None:
    """Emit one structured progress line to stderr, keeping stdout for the result."""

    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _training_config_payload(training: TrainingConfig) -> dict[str, object]:
    """Render the frozen fine-tuning hyperparameters recorded in `config.json`."""

    return {
        "epochs": training.epochs,
        "eval_batch_size": training.eval_batch_size,
        "learning_rate": training.learning_rate,
        "max_grad_norm": training.max_grad_norm,
        "max_sequence_length": training.max_sequence_length,
        "selection_metric": training.selection_metric,
        "threshold_source": training.threshold_source,
        "train_batch_size": training.train_batch_size,
        "warmup_ratio": training.warmup_ratio,
        "weight_decay": training.weight_decay,
    }


def _threshold_config_payload(threshold: ThresholdConfig) -> dict[str, object]:
    """Render the frozen threshold-selection policy."""

    return {
        "minimum_coverage": threshold.minimum_coverage,
        "objective": threshold.objective,
    }


def _artifact_config_payload(config: FoundationConfig) -> dict[str, object]:
    """Render the complete frozen configuration persisted inside the bundle."""

    return {
        "base_model_id": config.base_model_id,
        "base_model_revision": config.base_model_revision,
        "threshold": _threshold_config_payload(config.threshold),
        "training": _training_config_payload(config.training),
    }


def _run_identity_payload(
    config: FoundationConfig, prepared: PreparedDataset
) -> dict[str, object]:
    """Render every input that changes what the bundle contains.

    A bundle is immutable and `make train` reuses one whose run ID already exists,
    so any input that changes the bundle's contents without changing the ID would
    leave a stale artifact in place while this run reported success.

    `base_model_revision` is included because the weights start from it. The
    threshold policy is included even though it does not affect the fitted model:
    it selects the value written to `threshold.json`, which serving acts on, so a
    changed coverage floor must produce a new bundle rather than silently reuse
    the old threshold.
    """

    return {
        "base_model_id": config.base_model_id,
        "base_model_revision": config.base_model_revision,
        "seed": config.seed,
        "split_fingerprints": prepared.provenance["split_fingerprints"],
        "threshold": _threshold_config_payload(config.threshold),
        "training": _training_config_payload(config.training),
        "validation_fraction": config.validation_fraction,
    }


def _texts_and_labels(
    examples: tuple[CanonicalExample, ...],
) -> tuple[list[str], list[int]]:
    return [example.text for example in examples], [example.label_id for example in examples]


def _example_id_hash(examples: tuple[CanonicalExample, ...]) -> str:
    """Hash the evaluated example IDs so a report names the exact items it scored."""

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


def _correctness(predicted: list[int], truth: list[int]) -> list[bool]:
    """Pair predictions with labels positionally, refusing a length mismatch."""

    return [bool(left == right) for left, right in zip(predicted, truth, strict=True)]


def _validation_record(
    *,
    metrics: ClassificationMetrics,
    epoch_records: list[dict[str, object]],
    selected_epoch: int,
    selection_metric: str,
    example_id_hash: str,
    label_ids: list[int],
    predicted_label_ids: list[int],
    confidences: list[float],
    correct: list[bool],
) -> dict[str, object]:
    """Render `validation_metrics.json`, including the per-example predictions.

    `REQUIREMENTS.md` AC-003 requires the bundle to contain validation
    predictions, while the bundle layout in `ML_SYSTEM_DESIGN.md` lists no
    separate predictions file. Requirements outrank the design document, so the
    predictions are carried inside this file rather than by adding a file the
    approved layout does not have.

    Keeping them also makes the threshold replayable: the coverage curve and the
    selection can be recomputed from this record alone, with no model load and no
    access to any split other than validation.
    """

    return {
        "metric_version": METRIC_VERSION,
        "split": "validation",
        "selection_metric": selection_metric,
        "selected_epoch": selected_epoch,
        "epochs": epoch_records,
        "metrics": metrics_payload(metrics),
        "predictions": {
            "example_count": len(confidences),
            "example_id_sha256": example_id_hash,
            "label_ids": label_ids,
            "predicted_label_ids": predicted_label_ids,
            "confidences": confidences,
            "correct": correct,
        },
    }


def _curve_payload(curve: tuple[CoveragePoint, ...]) -> list[dict[str, object]]:
    """Render the full risk/coverage curve so the coverage floor can be challenged."""

    return [
        {
            "threshold": point.threshold,
            "coverage": point.coverage,
            "accepted_count": point.accepted_count,
            "accepted_accuracy": point.accepted_accuracy,
            "selective_risk": point.selective_risk,
        }
        for point in curve
    ]


def _curve_from_bundle(bundle: ArtifactBundle) -> tuple[CoveragePoint, ...]:
    """Recompute the coverage curve from the bundle's persisted validation record.

    Used on the reuse path, so a report can be rebuilt without loading weights and
    without touching any split.
    """

    if bundle.validation_metrics is None:
        raise ArtifactError(f"Bundle {bundle.run_id} carries no validation metrics")
    predictions = bundle.validation_metrics.get("predictions")
    if not isinstance(predictions, dict):
        raise ArtifactError(f"Bundle {bundle.run_id} carries no validation predictions")

    confidences = predictions.get("confidences")
    correct = predictions.get("correct")
    if not isinstance(confidences, list) or not isinstance(correct, list):
        raise ArtifactError(f"Bundle {bundle.run_id} has an unusable validation record")
    return coverage_curve(
        [float(value) for value in confidences], [bool(value) for value in correct]
    )


def _train_one_epoch(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    optimizer: torch.optim.Optimizer,
    schedule: torch.optim.lr_scheduler.LRScheduler,
    *,
    texts: list[str],
    label_ids: list[int],
    label_count: int,
    config: FoundationConfig,
    epoch: int,
    device: torch.device,
) -> float:
    """Run one epoch of the plain PyTorch loop and return its mean training loss.

    `transformers.Trainer` is not used: `TrainingArguments` requires
    `accelerate>=1.1.0`, which is not in `uv.lock`, and E04 adds no dependency
    (decision D9). Every optimisation step is therefore explicit here.
    """

    model.train()
    total_loss = 0.0
    step_count = 0
    for batch_texts, batch_labels in train_batches(
        texts,
        label_ids,
        label_count=label_count,
        training=config.training,
        seed=config.seed,
        epoch=epoch,
    ):
        batch = encode(
            tokenizer,
            batch_texts,
            max_sequence_length=config.training.max_sequence_length,
        )
        loss, _ = forward_loss(
            model,
            {key: value.to(device) for key, value in batch.items()},
            torch.tensor(batch_labels, dtype=torch.long, device=device),
        )
        loss.backward()  # type: ignore[no-untyped-call]
        torch.nn.utils.clip_grad_norm_(model.parameters(), config.training.max_grad_norm)
        optimizer.step()
        schedule.step()
        optimizer.zero_grad(set_to_none=True)

        total_loss += float(loss.item())
        step_count += 1
        if step_count % PROGRESS_EVERY_STEPS == 0:
            _log(
                {
                    "epoch": epoch,
                    "step": step_count,
                    "learning_rate": float(optimizer.param_groups[0]["lr"]),
                    "mean_loss_so_far": total_loss / step_count,
                }
            )

    if step_count == 0:  # pragma: no cover - `batch_slices` rejects an empty split
        raise TrainingError("Epoch produced no optimisation steps")
    return total_loss / step_count


def _fit(
    config: FoundationConfig,
    prepared: PreparedDataset,
    device: torch.device,
) -> tuple[
    PreTrainedTokenizerBase, PreTrainedModel, list[dict[str, object]], int, float
]:
    """Fine-tune the pinned base model and restore the best validation epoch.

    Selection uses `config.training.selection_metric`, which the configuration
    loader constrains to a validation metric, and a strictly-greater comparison,
    so the earliest epoch reaching the best score wins and a later epoch that
    merely ties does not displace it.
    """

    label_count = len(prepared.label_names)
    train_texts, train_labels = _texts_and_labels(prepared.train)
    validation_texts, validation_labels = _texts_and_labels(prepared.validation)

    seed_training(config.seed)
    tokenizer = load_tokenizer(config)
    model = move_to_device(load_model(config, prepared.label_names), device)

    total_steps = total_optimisation_steps(len(train_texts), config.training)
    optimizer = build_optimizer(model, config.training)
    schedule = build_schedule(optimizer, config.training, total_steps=total_steps)
    _log(
        {
            "event": "training_started",
            "train_examples": len(train_texts),
            "validation_examples": len(validation_texts),
            "total_optimisation_steps": total_steps,
        }
    )

    epoch_records: list[dict[str, object]] = []
    best_state: dict[str, torch.Tensor] | None = None
    best_score = -1.0
    best_epoch = -1
    for epoch in range(config.training.epochs):
        mean_loss = _train_one_epoch(
            model,
            tokenizer,
            optimizer,
            schedule,
            texts=train_texts,
            label_ids=train_labels,
            label_count=label_count,
            config=config,
            epoch=epoch,
            device=device,
        )
        probabilities = predict_probabilities(
            model,
            tokenizer,
            validation_texts,
            label_count=label_count,
            training=config.training,
            device=device,
        )
        metrics = compute_classification_metrics(
            validation_labels,
            labels_from_probabilities(probabilities),
            prepared.label_names,
        )
        epoch_records.append(
            {
                "epoch": epoch,
                "mean_training_loss": mean_loss,
                "validation_accuracy": metrics.accuracy,
                "validation_macro_f1": metrics.macro_f1,
                "validation_weighted_f1": metrics.weighted_f1,
            }
        )
        _log({"event": "epoch_completed", **epoch_records[-1]})

        if metrics.macro_f1 > best_score:
            best_score = metrics.macro_f1
            best_epoch = epoch
            best_state = {
                name: tensor.detach().clone().cpu()
                for name, tensor in model.state_dict().items()
            }

    if best_state is None:  # pragma: no cover - `epochs` is a positive integer
        raise TrainingError("Training completed without selecting an epoch")
    model.load_state_dict(best_state)
    return tokenizer, model, epoch_records, best_epoch, best_score


def _save_bundle(
    config: FoundationConfig,
    prepared: PreparedDataset,
    run_id: str,
    *,
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    threshold: dict[str, object],
    validation_metrics: dict[str, object],
    runtime: dict[str, object],
) -> ArtifactBundle:
    provenance: dict[str, object] = {
        "artifact_name": ARTIFACT_NAME,
        "base_model_id": config.base_model_id,
        "base_model_revision": config.base_model_revision,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": config.dataset_id,
        "dataset_revision": config.dataset_revision,
        "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
        "derived_split_counts": prepared.provenance["derived_split_counts"],
        "label_map_hash": label_map_hash(prepared.label_names),
        "label_map_sha256": prepared.provenance["label_map_sha256"],
        "model_payload": MODEL_DIRECTORY,
        "python_version": platform.python_version(),
        "run_id": run_id,
        "runtime": runtime,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "seed": config.seed,
        "split_fingerprints": prepared.provenance["split_fingerprints"],
        "tokenizer_payload": TOKENIZER_DIRECTORY,
        "trained_on_split": "train",
        "validation_fraction": config.validation_fraction,
        "validation_selection_split": "validation",
    }

    def _write_payload(staging: Path) -> None:
        model.save_pretrained(staging / MODEL_DIRECTORY, safe_serialization=True)
        tokenizer.save_pretrained(staging / TOKENIZER_DIRECTORY)

    return save_artifact(
        artifact_root=config.artifact_root,
        artifact_name=ARTIFACT_NAME,
        run_id=run_id,
        config=_artifact_config_payload(config),
        label_names=prepared.label_names,
        provenance=provenance,
        write_payload=_write_payload,
        threshold=threshold,
        validation_metrics=validation_metrics,
    )


def _verify_reload_parity(
    bundle: ArtifactBundle,
    config: FoundationConfig,
    prepared: PreparedDataset,
    *,
    reference_probabilities: np.ndarray,
    device: torch.device,
) -> None:
    """Reload from disk and prove the restored bundle behaves like the fitted model.

    Parity is checked on validation data, and it deliberately includes the
    accept/abstain decision rather than stopping at the probabilities. Serving's
    observable output is that decision, so a threshold that failed to persist, or
    a boundary applied inconsistently, must fail this run instead of surfacing as
    a wrong answer from the API.
    """

    validation_texts, validation_labels = _texts_and_labels(prepared.validation)
    tokenizer = load_tokenizer_from_directory(bundle.directory_path(TOKENIZER_DIRECTORY))
    model = move_to_device(
        load_model_from_directory(bundle.directory_path(MODEL_DIRECTORY), prepared.label_names),
        device,
    )

    probabilities = predict_probabilities(
        model,
        tokenizer,
        validation_texts,
        label_count=len(prepared.label_names),
        training=config.training,
        device=device,
    )

    reloaded_labels = labels_from_probabilities(probabilities)
    if reloaded_labels != labels_from_probabilities(reference_probabilities):
        raise ArtifactError("Reloaded transformer produced different labels than the fitted model")
    if not np.allclose(
        probabilities, reference_probabilities, atol=RELOAD_PROBABILITY_TOLERANCE, rtol=0.0
    ):
        raise ArtifactError(
            "Reloaded transformer probabilities diverged beyond the approved tolerance"
        )

    threshold = bundle.selected_threshold()
    reference_confidences = confidences_from_probabilities(reference_probabilities)
    reference_decisions = [decide(value, threshold) for value in reference_confidences]
    reloaded_decisions = [
        decide(value, threshold) for value in confidences_from_probabilities(probabilities)
    ]
    if reference_decisions != reloaded_decisions:
        raise ArtifactError("Reloaded transformer changed at least one accept/abstain decision")

    accepted = sum(1 for decision in reloaded_decisions if decision == "accept")
    _log(
        {
            "event": "reload_parity_verified",
            "accepted_from_reloaded_artifact": accepted,
            "example_count": len(reloaded_decisions),
            "labels_identical": True,
            "reloaded_accuracy": float(
                np.count_nonzero(np.asarray(reloaded_labels) == np.asarray(validation_labels))
            )
            / len(validation_labels),
        }
    )


def _report_payload(
    config: FoundationConfig,
    prepared: PreparedDataset,
    bundle: ArtifactBundle,
    *,
    curve: tuple[CoveragePoint, ...],
    runtime: dict[str, object],
) -> dict[str, object]:
    """Render the training report, which contains no test-derived quantity.

    The full risk/coverage curve is included so the `0.70` coverage floor is
    visible as a policy choice rather than an unexamined constant.
    """

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "metric_version": METRIC_VERSION,
        "artifact_name": bundle.artifact_name,
        "run_id": bundle.run_id,
        "artifact_directory": str(bundle.directory),
        "split": "validation",
        "base_model_id": config.base_model_id,
        "base_model_revision": config.base_model_revision,
        "dataset_id": config.dataset_id,
        "dataset_revision": config.dataset_revision,
        "split_fingerprints": prepared.provenance["split_fingerprints"],
        "label_map_sha256": prepared.provenance["label_map_sha256"],
        "label_map_hash": label_map_hash(prepared.label_names),
        "validation_example_id_sha256": _example_id_hash(prepared.validation),
        "dependency_versions": dependency_versions(TRACKED_DEPENDENCIES),
        "python_version": platform.python_version(),
        "runtime": runtime,
        "seed": config.seed,
        "config": _artifact_config_payload(config),
        "threshold": bundle.threshold,
        "validation": bundle.validation_metrics,
        "coverage_curve": _curve_payload(curve),
    }


def _fresh_run(
    config: FoundationConfig,
    prepared: PreparedDataset,
    run_id: str,
    device: torch.device,
) -> tuple[ArtifactBundle, tuple[CoveragePoint, ...], dict[str, object]]:
    """Fine-tune, select the threshold, seal the bundle, and verify it reloads."""

    validation_texts, validation_labels = _texts_and_labels(prepared.validation)
    tokenizer, model, epoch_records, best_epoch, best_score = _fit(config, prepared, device)

    # The authoritative validation pass runs on the restored weights, so what is
    # measured, thresholded, and saved are all the same model.
    probabilities = predict_probabilities(
        model,
        tokenizer,
        validation_texts,
        label_count=len(prepared.label_names),
        training=config.training,
        device=device,
    )
    if probabilities.shape[0] != len(validation_texts):
        raise TrainingError("Validation predictions do not cover every validation example")

    predicted = labels_from_probabilities(probabilities)
    confidences = confidences_from_probabilities(probabilities)
    metrics = compute_classification_metrics(validation_labels, predicted, prepared.label_names)
    if abs(metrics.macro_f1 - best_score) > SELECTION_METRIC_TOLERANCE:
        raise TrainingError(
            f"Restored epoch {best_epoch} scores {metrics.macro_f1}, not the selected {best_score}"
        )

    correct = _correctness(predicted, validation_labels)
    selection: ThresholdSelection = select_threshold(
        confidences, correct, minimum_coverage=config.threshold.minimum_coverage
    )
    curve = coverage_curve(confidences, correct)
    _log({"event": "threshold_selected", **selection_payload(selection)})

    runtime = runtime_payload(runtime_facts(device))
    bundle = _save_bundle(
        config,
        prepared,
        run_id,
        model=model,
        tokenizer=tokenizer,
        threshold=selection_payload(selection),
        validation_metrics=_validation_record(
            metrics=metrics,
            epoch_records=epoch_records,
            selected_epoch=best_epoch,
            selection_metric=config.training.selection_metric,
            example_id_hash=_example_id_hash(prepared.validation),
            label_ids=validation_labels,
            predicted_label_ids=predicted,
            confidences=confidences,
            correct=correct,
        ),
        runtime=runtime,
    )
    if bundle.selected_threshold() != selection.threshold:
        raise ArtifactError("Sealed bundle does not carry the selected threshold")

    _verify_reload_parity(
        bundle, config, prepared, reference_probabilities=probabilities, device=device
    )
    return bundle, curve, runtime


def main() -> None:
    """Run the complete transformer lifecycle and write one machine-readable report."""

    config = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
    prepared = prepare_dataset(load_pinned_dataset(config), config)
    device = resolve_device()

    run_id = compute_run_id(
        ARTIFACT_NAME, config.dataset_revision, _run_identity_payload(config, prepared)
    )
    destination = artifact_directory(config.artifact_root, ARTIFACT_NAME, run_id)
    if destination.exists():
        # An existing bundle is immutable and its run ID covers every input that
        # would change it, so it is reused rather than retrained. The report is
        # rebuilt from the bundle's own validation record, with no model load.
        bundle = load_artifact(destination)
        curve = _curve_from_bundle(bundle)
        runtime = runtime_payload(runtime_facts(device))
        _log({"event": "artifact_reused", "run_id": bundle.run_id})
    else:
        bundle, curve, runtime = _fresh_run(config, prepared, run_id, device)

    report_path = config.report_root / "train" / bundle.run_id / REPORT_FILENAME
    _write_json_atomically(
        report_path,
        _report_payload(config, prepared, bundle, curve=curve, runtime=runtime),
    )

    threshold_record = bundle.threshold or {}
    print(
        json.dumps(
            {
                "artifact_directory": str(bundle.directory),
                "device": runtime["device"],
                "gpu_throughput_claim": "unevidenced",
                "report_path": str(report_path),
                "run_id": bundle.run_id,
                "threshold": bundle.selected_threshold(),
                "validation_accepted_accuracy": threshold_record.get("accepted_accuracy"),
                "validation_coverage": threshold_record.get("coverage"),
                "validation_selective_risk": threshold_record.get("selective_risk"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ArtifactError, DataContractError, ThresholdError, TrainingError, ValueError) as error:
        raise SystemExit(f"Transformer training failed: {error}") from error
