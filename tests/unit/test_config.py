import tomllib
from pathlib import Path
from typing import Any

import pytest

from intentguard.config import (
    BANKING77_DATASET_ID,
    BANKING77_DATASET_REVISION,
    STATUS_VOCABULARY,
    UNRESOLVED_REVISION,
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
    assert config.base_model_id == "distilbert/distilbert-base-uncased"
    assert config.base_model_revision == UNRESOLVED_REVISION
    assert config.status_vocabulary == STATUS_VOCABULARY


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
