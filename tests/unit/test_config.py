import tomllib
from pathlib import Path
from typing import Any

import pytest

from intentguard.config import (
    BANKING77_DATASET_ID,
    BANKING77_DATASET_REVISION,
    DISTILBERT_BASE_MODEL_ID,
    DISTILBERT_BASE_MODEL_REVISION,
    STATUS_VOCABULARY,
    load_foundation_config,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPOSITORY_ROOT / "configs" / "default.toml"


def test_default_configuration_loads_foundation_contract() -> None:
    config = load_foundation_config(DEFAULT_CONFIG)

    assert config.seed == 42
    assert config.dataset_id == BANKING77_DATASET_ID
    assert config.dataset_revision == BANKING77_DATASET_REVISION
    assert config.validation_fraction == 0.15
    assert config.data_root == Path("data")
    assert config.artifact_root == Path("artifacts")
    assert config.report_root == Path("reports")
    assert config.base_model_id == DISTILBERT_BASE_MODEL_ID
    assert config.base_model_revision == DISTILBERT_BASE_MODEL_REVISION
    assert config.status_vocabulary == STATUS_VOCABULARY


def test_base_model_revision_is_an_immutable_commit_pin() -> None:
    revision = load_foundation_config(DEFAULT_CONFIG).base_model_revision

    # A mutable ref such as `main` would silently change the trained weights
    # between runs while leaving the recorded provenance unchanged.
    assert len(revision) == 40
    assert set(revision) <= set("0123456789abcdef")


def test_default_configuration_resolves_every_training_hyperparameter() -> None:
    training = load_foundation_config(DEFAULT_CONFIG).training

    assert training.max_sequence_length == 96
    assert training.epochs == 2
    assert training.train_batch_size == 16
    assert training.eval_batch_size == 32
    assert training.learning_rate == 2e-5
    assert training.weight_decay == 0.01
    assert training.warmup_ratio == 0.1
    assert training.max_grad_norm == 1.0
    assert training.selection_metric == "validation_macro_f1"
    assert training.threshold_source == "validation"


def test_default_configuration_resolves_the_threshold_policy() -> None:
    threshold = load_foundation_config(DEFAULT_CONFIG).threshold

    assert threshold.minimum_coverage == 0.70
    assert threshold.objective == "selective_risk"


def test_default_configuration_resolves_every_baseline_hyperparameter() -> None:
    baseline = load_foundation_config(DEFAULT_CONFIG).baseline

    assert baseline.lowercase is True
    assert baseline.ngram_min == 1
    assert baseline.ngram_max == 2
    assert baseline.max_features == 50_000
    assert baseline.min_df == 1
    assert baseline.sublinear_tf is True
    assert baseline.solver == "lbfgs"
    assert baseline.regularization_c == 1.0
    assert baseline.max_iter == 1_000
    assert baseline.class_weight == "balanced"


def _write_config(path: Path, document: dict[str, Any]) -> Path:
    def render(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, list):
            return "[" + ", ".join(render(item) for item in value) + "]"
        return str(value)

    lines: list[str] = []
    for table, entries in document.items():
        lines.append(f"[{table}]")
        lines.extend(f"{key} = {render(value)}" for key, value in entries.items())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _default_document() -> dict[str, Any]:
    with DEFAULT_CONFIG.open("rb") as stream:
        return tomllib.load(stream)


@pytest.mark.parametrize(
    "key",
    [
        "lowercase",
        "ngram_min",
        "ngram_max",
        "max_features",
        "min_df",
        "sublinear_tf",
        "solver",
        "regularization_c",
        "max_iter",
        "class_weight",
    ],
)
def test_missing_baseline_hyperparameter_is_rejected(tmp_path: Path, key: str) -> None:
    document = _default_document()
    del document["baseline"][key]

    with pytest.raises(ValueError, match=key):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("lowercase", "yes"),
        ("ngram_min", 0),
        ("max_features", -1),
        ("min_df", 0),
        ("sublinear_tf", 1),
        ("solver", "newton-cholesky"),
        ("regularization_c", 0.0),
        # `nan <= 0.0` is false and `inf` is positive, so a sign check alone
        # lets both reach the estimator. Finiteness is required explicitly.
        ("regularization_c", float("nan")),
        ("regularization_c", float("inf")),
        ("max_iter", 0),
        ("class_weight", "auto"),
    ],
)
def test_invalid_baseline_hyperparameter_is_rejected(
    tmp_path: Path, key: str, value: object
) -> None:
    document = _default_document()
    document["baseline"][key] = value

    with pytest.raises(ValueError):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_inverted_ngram_range_is_rejected(tmp_path: Path) -> None:
    document = _default_document()
    document["baseline"]["ngram_min"] = 3
    document["baseline"]["ngram_max"] = 2

    with pytest.raises(ValueError, match="ngram_min"):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_class_weight_none_resolves_to_no_weighting(tmp_path: Path) -> None:
    document = _default_document()
    document["baseline"]["class_weight"] = "none"

    config = load_foundation_config(_write_config(tmp_path / "config.toml", document))

    assert config.baseline.class_weight is None


def test_missing_baseline_table_is_rejected(tmp_path: Path) -> None:
    document = _default_document()
    del document["baseline"]

    with pytest.raises(ValueError, match="baseline"):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize("key", ["artifact_root", "report_root"])
def test_missing_generated_output_root_is_rejected(tmp_path: Path, key: str) -> None:
    document = _default_document()
    del document["paths"][key]

    with pytest.raises(ValueError, match=key):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize(
    "key",
    [
        "max_sequence_length",
        "epochs",
        "train_batch_size",
        "eval_batch_size",
        "learning_rate",
        "weight_decay",
        "warmup_ratio",
        "max_grad_norm",
        "selection_metric",
        "threshold_source",
    ],
)
def test_missing_training_hyperparameter_is_rejected(tmp_path: Path, key: str) -> None:
    document = _default_document()
    del document["training"][key]

    with pytest.raises(ValueError, match=key):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_sequence_length", 0),
        ("epochs", 0),
        ("epochs", 1.5),
        ("train_batch_size", 0),
        ("eval_batch_size", -1),
        ("learning_rate", 0.0),
        ("learning_rate", float("nan")),
        ("learning_rate", float("inf")),
        ("weight_decay", -0.01),
        ("weight_decay", float("nan")),
        # A warmup ratio of 1.0 would leave no decay steps at all.
        ("warmup_ratio", 1.0),
        ("warmup_ratio", -0.1),
        ("warmup_ratio", float("inf")),
        ("max_grad_norm", 0.0),
        ("max_grad_norm", float("nan")),
        # Only a validation-derived metric may select the checkpoint.
        ("selection_metric", "test_macro_f1"),
        # Only validation may source the threshold; test selection is leakage.
        ("threshold_source", "test"),
    ],
)
def test_invalid_training_hyperparameter_is_rejected(
    tmp_path: Path, key: str, value: object
) -> None:
    document = _default_document()
    document["training"][key] = value

    with pytest.raises(ValueError):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_zero_warmup_ratio_is_accepted(tmp_path: Path) -> None:
    document = _default_document()
    document["training"]["warmup_ratio"] = 0.0

    config = load_foundation_config(_write_config(tmp_path / "config.toml", document))

    assert config.training.warmup_ratio == 0.0


def test_zero_weight_decay_is_accepted(tmp_path: Path) -> None:
    document = _default_document()
    document["training"]["weight_decay"] = 0.0

    config = load_foundation_config(_write_config(tmp_path / "config.toml", document))

    assert config.training.weight_decay == 0.0


@pytest.mark.parametrize("key", ["minimum_coverage", "objective"])
def test_missing_threshold_setting_is_rejected(tmp_path: Path, key: str) -> None:
    document = _default_document()
    del document["threshold"][key]

    with pytest.raises(ValueError, match=key):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("minimum_coverage", 0.0),
        ("minimum_coverage", 1.0),
        ("minimum_coverage", -0.1),
        ("minimum_coverage", float("nan")),
        ("objective", "accuracy"),
    ],
)
def test_invalid_threshold_setting_is_rejected(tmp_path: Path, key: str, value: object) -> None:
    document = _default_document()
    document["threshold"][key] = value

    with pytest.raises(ValueError):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


@pytest.mark.parametrize("table", ["training", "threshold"])
def test_missing_model_table_is_rejected(tmp_path: Path, table: str) -> None:
    document = _default_document()
    del document[table]

    with pytest.raises(ValueError, match=table):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_unpinned_base_model_revision_is_rejected(tmp_path: Path) -> None:
    document = _default_document()
    document["model"]["base_model_revision"] = "UNRESOLVED"

    with pytest.raises(ValueError, match="revision"):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_mutable_base_model_ref_is_rejected(tmp_path: Path) -> None:
    document = _default_document()
    document["model"]["base_model_revision"] = "main"

    with pytest.raises(ValueError, match="revision"):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))


def test_unapproved_base_model_identifier_is_rejected(tmp_path: Path) -> None:
    document = _default_document()
    document["model"]["base_model_id"] = "bert-base-uncased"

    with pytest.raises(ValueError, match="identifier"):
        load_foundation_config(_write_config(tmp_path / "config.toml", document))
