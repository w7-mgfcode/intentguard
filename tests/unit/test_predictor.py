"""Predictor guards that need no weights (S06.2).

Everything here runs on CI without the 265 MB bundle: root resolution, bundle
selection, the label-map and threshold checks, and the truncation comparison. The
real-artifact behaviour lives in `tests/integration/test_api.py`, which skips when
no bundle is configured — so these tests are what keep the guards covered on a
machine that has never trained.

The bundles built here carry stub payload files rather than real weights, because
none of these checks depend on the weights being genuine. Anything that does load a
model is in the integration suite by design.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import torch

from intentguard.artifacts import (
    ArtifactBundle,
    ArtifactError,
    label_map_hash,
    load_artifact,
    save_artifact,
)
from intentguard.config import (
    TrainingConfig,
    load_foundation_config,
    training_config_from_payload,
)
from intentguard.data import CANONICAL_LABEL_NAMES, LABEL_COUNT
from intentguard.predictor import (
    ARTIFACT_ROOT_VARIABLE,
    TRANSFORMER_ARTIFACT_NAME,
    ArtifactPrediction,
    ArtifactPredictor,
    PredictorError,
    _persisted_training_config,
    _validated_label_names,
    _validated_threshold,
    locate_transformer_bundle,
    resolve_artifact_root,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG = load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml")
DATASET_REVISION = "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
RUN_ID = f"{TRANSFORMER_ARTIFACT_NAME}-1fb62b1bb463-abcdef123456"


def _training_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "max_sequence_length": 96,
        "epochs": 2,
        "train_batch_size": 16,
        "eval_batch_size": 32,
        "learning_rate": 2e-5,
        "weight_decay": 0.01,
        "warmup_ratio": 0.1,
        "max_grad_norm": 1.0,
        "selection_metric": "validation_macro_f1",
        "threshold_source": "validation",
    }
    payload.update(overrides)
    return payload


def _threshold_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "threshold": 0.16841767053420467,
        "rule": "min_selective_risk_at_min_coverage",
        "rule_version": 1,
        "source": "validation",
        "minimum_coverage": 0.70,
        "validation_example_count": 1501,
        "coverage": 0.7015323117921386,
        "accepted_count": 1053,
        "accepted_accuracy": 0.8395061728395061,
        "selective_risk": 0.16049382716049387,
        "candidate_count": 1503,
    }
    payload.update(overrides)
    return payload


def _write_payload(staging: Path) -> None:
    for name in ("model", "tokenizer"):
        directory = staging / name
        directory.mkdir()
        (directory / "config.json").write_text("{}\n", encoding="utf-8")


def _save_bundle(
    root: Path,
    *,
    label_names: Sequence[str] = CANONICAL_LABEL_NAMES,
    config: dict[str, Any] | None = None,
    threshold: dict[str, Any] | None = None,
    run_id: str = RUN_ID,
) -> ArtifactBundle:
    return save_artifact(
        artifact_root=root,
        artifact_name=TRANSFORMER_ARTIFACT_NAME,
        run_id=run_id,
        config=config if config is not None else {"training": _training_payload()},
        label_names=label_names,
        provenance={
            "artifact_name": TRANSFORMER_ARTIFACT_NAME,
            "created_at": "2026-01-01T00:00:00+00:00",
            "dataset_id": "PolyAI/banking77",
            "dataset_revision": DATASET_REVISION,
            "dependency_versions": {"torch": "2.13.0+cpu", "transformers": "5.14.1"},
            "label_map_hash": label_map_hash(label_names),
            "run_id": run_id,
            "seed": 42,
            "split_fingerprints": {
                "train": "a" * 64,
                "validation": "b" * 64,
                "test": "c" * 64,
            },
        },
        write_payload=_write_payload,
        threshold=_threshold_payload() if threshold is None else threshold,
    )


# --------------------------------------------------------------------------------
# Artifact-root resolution
# --------------------------------------------------------------------------------


def test_unset_environment_variable_falls_back_to_the_configured_root() -> None:
    assert resolve_artifact_root(CONFIG, {}) == CONFIG.artifact_root


@pytest.mark.parametrize("value", ["", "   ", "\t"])
def test_blank_environment_variable_is_treated_as_unset(value: str) -> None:
    # A shell that exports the variable without a value must not resolve the root to
    # the current working directory, which is what `Path("")` would do.
    assert resolve_artifact_root(CONFIG, {ARTIFACT_ROOT_VARIABLE: value}) == CONFIG.artifact_root


def test_set_environment_variable_overrides_the_configured_root(tmp_path: Path) -> None:
    resolved = resolve_artifact_root(CONFIG, {ARTIFACT_ROOT_VARIABLE: str(tmp_path)})

    assert resolved == tmp_path
    assert resolved != CONFIG.artifact_root


def test_user_home_is_expanded() -> None:
    resolved = resolve_artifact_root(CONFIG, {ARTIFACT_ROOT_VARIABLE: "~/artifacts"})

    assert "~" not in str(resolved)
    assert resolved.is_absolute()


def test_resolution_reads_the_process_environment_when_none_is_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ARTIFACT_ROOT_VARIABLE, str(tmp_path))

    assert resolve_artifact_root(CONFIG) == tmp_path


# --------------------------------------------------------------------------------
# Bundle selection
# --------------------------------------------------------------------------------


def test_absent_artifact_directory_names_the_variable_to_set(tmp_path: Path) -> None:
    with pytest.raises(PredictorError, match=ARTIFACT_ROOT_VARIABLE):
        locate_transformer_bundle(tmp_path)


def test_empty_artifact_directory_is_refused(tmp_path: Path) -> None:
    (tmp_path / TRANSFORMER_ARTIFACT_NAME).mkdir()

    with pytest.raises(PredictorError, match="No intentguard-distilbert bundle"):
        locate_transformer_bundle(tmp_path)


def test_single_bundle_is_located(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path)

    assert locate_transformer_bundle(tmp_path) == bundle.directory


def test_two_bundles_are_refused_and_both_are_named(tmp_path: Path) -> None:
    parent = tmp_path / TRANSFORMER_ARTIFACT_NAME
    parent.mkdir()
    (parent / f"{TRANSFORMER_ARTIFACT_NAME}-aaaaaaaaaaaa-111111111111").mkdir()
    (parent / f"{TRANSFORMER_ARTIFACT_NAME}-aaaaaaaaaaaa-222222222222").mkdir()

    with pytest.raises(PredictorError) as error:
        locate_transformer_bundle(tmp_path)

    # Naming them is the point: an operator has to know which to remove.
    assert "111111111111" in str(error.value)
    assert "222222222222" in str(error.value)


def test_a_loose_file_beside_a_bundle_is_ignored(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path)
    (tmp_path / TRANSFORMER_ARTIFACT_NAME / "notes.txt").write_text("x\n", encoding="utf-8")

    # Only directories are candidates, so a stray file must not make the choice
    # ambiguous and stop startup.
    assert locate_transformer_bundle(tmp_path) == bundle.directory


# --------------------------------------------------------------------------------
# Label-map validation
# --------------------------------------------------------------------------------


def test_canonical_label_map_is_accepted(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path)

    assert _validated_label_names(bundle) == CANONICAL_LABEL_NAMES
    assert len(_validated_label_names(bundle)) == LABEL_COUNT


def test_a_bundle_with_the_wrong_label_count_is_refused(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path, label_names=CANONICAL_LABEL_NAMES[:76])

    with pytest.raises(PredictorError, match="maps 76 labels, not 77"):
        _validated_label_names(bundle)


def test_a_reordered_77_label_map_is_refused(tmp_path: Path) -> None:
    """77 labels in the wrong order would produce confidently mislabelled predictions.

    The count check alone accepts this, which is why the ordered map is compared: the
    label map is what fixes the probability column order.
    """

    reordered = (*CANONICAL_LABEL_NAMES[1:], CANONICAL_LABEL_NAMES[0])
    bundle = _save_bundle(tmp_path, label_names=reordered)

    assert len(reordered) == LABEL_COUNT
    with pytest.raises(PredictorError, match="canonical BANKING77 label map"):
        _validated_label_names(bundle)


# --------------------------------------------------------------------------------
# Threshold validation
# --------------------------------------------------------------------------------


def test_validation_sourced_threshold_is_returned(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path)

    assert _validated_threshold(bundle) == pytest.approx(0.16841767053420467)


def test_a_bundle_without_a_threshold_cannot_be_served(tmp_path: Path) -> None:
    """A baseline-shaped bundle loads, but serving must refuse to invent a default."""

    bundle = _save_bundle(tmp_path)
    without = replace(bundle, threshold=None)

    with pytest.raises(PredictorError, match="no selected threshold"):
        _validated_threshold(without)


def test_a_test_sourced_threshold_is_refused_at_the_serving_boundary(
    tmp_path: Path,
) -> None:
    """The duplicate leakage check, exercised past `load_artifact`'s own guard.

    `load_artifact` rejects a test-sourced threshold first, so reaching this code needs
    a bundle mutated in memory. The duplicate is deliberate: this is the boundary where
    a leaked threshold would become a published decision.
    """

    bundle = _save_bundle(tmp_path)
    mutated = replace(bundle, threshold={**_threshold_payload(), "source": "test"})

    with pytest.raises(PredictorError, match="threshold source is 'test'"):
        _validated_threshold(mutated)


def test_a_test_sourced_threshold_on_disk_never_loads(tmp_path: Path) -> None:
    """The same property one layer lower, verified by mutating the file itself."""

    bundle = _save_bundle(tmp_path)
    path = bundle.directory / "threshold.json"
    original = path.read_text(encoding="utf-8")
    record = json.loads(original)
    record["source"] = "test"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # The checksum guard fires first, which is itself correct: the bundle is immutable.
    with pytest.raises(ArtifactError):
        load_artifact(bundle.directory)

    path.write_text(original, encoding="utf-8")
    assert load_artifact(bundle.directory).threshold is not None


# --------------------------------------------------------------------------------
# Persisted training configuration
# --------------------------------------------------------------------------------


def test_persisted_training_block_is_rebuilt_and_validated(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path)

    training = _persisted_training_config(bundle)

    assert isinstance(training, TrainingConfig)
    assert training.max_sequence_length == 96
    assert training.threshold_source == "validation"


def test_a_bundle_with_no_training_block_is_refused(tmp_path: Path) -> None:
    bundle = _save_bundle(tmp_path, config={"base_model_id": "distilbert/distilbert-base-uncased"})

    with pytest.raises(PredictorError, match="records no 'training' configuration"):
        _persisted_training_config(bundle)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_sequence_length", 0),
        ("max_sequence_length", "96"),
        ("threshold_source", "test"),
        ("selection_metric", "test_macro_f1"),
        ("learning_rate", float("nan")),
    ],
)
def test_an_invalid_persisted_training_block_is_refused(
    tmp_path: Path, key: str, value: object
) -> None:
    """A bundle's own configuration gets the same checks a TOML file does.

    `threshold_source = "test"` is the case that matters: a hand-edited bundle must not
    be able to declare a test-selected threshold and be served anyway.
    """

    bundle = _save_bundle(tmp_path, config={"training": _training_payload(**{key: value})})

    with pytest.raises(PredictorError, match="unusable training configuration"):
        _persisted_training_config(bundle)


def test_serving_reads_preprocessing_from_the_bundle_not_the_live_file(
    tmp_path: Path,
) -> None:
    """The bundle wins. `configs/default.toml` can be edited after a bundle is sealed."""

    bundle = _save_bundle(tmp_path, config={"training": _training_payload(max_sequence_length=32)})

    training = _persisted_training_config(bundle)

    assert training.max_sequence_length == 32
    assert CONFIG.training.max_sequence_length == 96


def test_training_config_from_payload_accepts_the_configured_block() -> None:
    """The shared validator must accept what `load_foundation_config` produced."""

    rebuilt = training_config_from_payload(_training_payload())

    assert rebuilt == CONFIG.training


# --------------------------------------------------------------------------------
# Truncation and the prediction record, without loading weights
# --------------------------------------------------------------------------------


class _LengthOnlyTokenizer:
    """A tokenizer stand-in that reports one token per character.

    Truncation reporting is a length comparison, so it is testable without the real
    vocabulary. `truncation=False` is asserted rather than honoured: a caller that
    truncated this pass would defeat the whole mechanism, and this double makes that
    mistake fail loudly.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, texts: Sequence[str], **kwargs: object) -> dict[str, list[list[int]]]:
        assert kwargs.get("truncation") is False, "the length pass must not truncate"
        self.calls.append(dict(kwargs))
        return {"input_ids": [list(range(len(text))) for text in texts]}


def _predictor_with(tokenizer: object, *, max_sequence_length: int = 10) -> ArtifactPredictor:
    """Build a predictor around a tokenizer double and a deliberately absent model.

    `model=None` is safe for the truncation tests because `input_truncated` never
    touches the model; a test that called `predict` would fail on it immediately
    rather than pass against a stub that cannot represent real inference.
    """

    return ArtifactPredictor(
        bundle=ArtifactBundle(
            artifact_name=TRANSFORMER_ARTIFACT_NAME,
            run_id=RUN_ID,
            directory=Path("/nonexistent"),
            config={"training": _training_payload(max_sequence_length=max_sequence_length)},
            label_names=CANONICAL_LABEL_NAMES,
            provenance={},
            payload_files=("model/config.json",),
            threshold=_threshold_payload(),
        ),
        model=None,  # type: ignore[arg-type]
        tokenizer=tokenizer,  # type: ignore[arg-type]
        label_names=CANONICAL_LABEL_NAMES,
        threshold=0.16841767053420467,
        training=training_config_from_payload(
            _training_payload(max_sequence_length=max_sequence_length)
        ),
        device=torch.device("cpu"),
    )


def test_truncation_is_reported_only_above_the_maximum_sequence_length() -> None:
    tokenizer = _LengthOnlyTokenizer()
    predictor = _predictor_with(tokenizer, max_sequence_length=10)

    assert predictor.input_truncated("x" * 9) is False
    # Exactly at the maximum is not truncated: nothing was dropped.
    assert predictor.input_truncated("x" * 10) is False
    assert predictor.input_truncated("x" * 11) is True


def test_the_length_pass_disables_truncation_and_the_length_warning() -> None:
    tokenizer = _LengthOnlyTokenizer()
    predictor = _predictor_with(tokenizer)

    predictor.input_truncated("x" * 20)

    assert tokenizer.calls == [{"truncation": False, "verbose": False}]


def test_metadata_is_read_from_the_bundle() -> None:
    predictor = _predictor_with(_LengthOnlyTokenizer())

    assert predictor.model_version == RUN_ID
    assert predictor.label_count == LABEL_COUNT
    assert predictor.device == "cpu"
    assert predictor.threshold == pytest.approx(0.16841767053420467)


def test_readiness_requires_a_full_length_label_map() -> None:
    predictor = _predictor_with(_LengthOnlyTokenizer())
    short = ArtifactPredictor(
        bundle=predictor.bundle,
        model=None,  # type: ignore[arg-type]
        tokenizer=_LengthOnlyTokenizer(),  # type: ignore[arg-type]
        label_names=CANONICAL_LABEL_NAMES[:10],
        threshold=0.5,
        training=CONFIG.training,
        device=torch.device("cpu"),
    )

    assert short.is_ready() is False


def test_prediction_record_satisfies_the_api_protocol_shape() -> None:
    """`ArtifactPrediction` must expose exactly what `api.Prediction` reads."""

    prediction = ArtifactPrediction(
        intent="activate_my_card",
        confidence=0.9,
        threshold=0.5,
        decision="accept",
        input_truncated=False,
    )

    for attribute in ("intent", "confidence", "threshold", "decision", "input_truncated"):
        assert hasattr(prediction, attribute)
    with pytest.raises(AttributeError):
        prediction.confidence = 0.1  # type: ignore[misc]
