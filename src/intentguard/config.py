"""Typed loading for repository-foundation configuration only."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

UNRESOLVED_REVISION: Final = "UNRESOLVED"
BANKING77_DATASET_ID: Final = "PolyAI/banking77"
BANKING77_DATASET_REVISION: Final = "1fb62b1bb4635df59a8e1b2f2bc5e0643b2856c8"
STATUS_VOCABULARY: Final = (
    "Implemented",
    "Measured",
    "Partial",
    "Mocked",
    "Blocked",
    "Planned",
)
APPROVED_BASELINE_SOLVERS: Final = ("lbfgs", "saga")
APPROVED_BASELINE_CLASS_WEIGHTS: Final = ("balanced", "none")


@dataclass(frozen=True)
class BaselineConfig:
    """Explicitly resolved TF-IDF logistic-regression hyperparameters.

    Every value is frozen in configuration before the canonical test split is
    read, so the E03 baseline is never tuned against test labels.
    """

    lowercase: bool
    ngram_min: int
    ngram_max: int
    max_features: int
    min_df: int
    sublinear_tf: bool
    solver: str
    regularization_c: float
    max_iter: int
    class_weight: str | None


@dataclass(frozen=True)
class FoundationConfig:
    """Typed project configuration required through the E02 data contract."""

    seed: int
    dataset_id: str
    dataset_revision: str
    validation_fraction: float
    data_root: Path
    artifact_root: Path
    report_root: Path
    base_model_id: str
    base_model_revision: str
    baseline: BaselineConfig
    status_vocabulary: tuple[str, ...]


def _table(document: dict[str, object], name: str) -> dict[str, object]:
    value = document.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"Missing or invalid [{name}] table")
    return cast(dict[str, object], value)


def _string(table: dict[str, object], name: str) -> str:
    value = table.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid string: {name}")
    return value


def _fraction(table: dict[str, object], name: str) -> float:
    value = table.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Missing or invalid fraction: {name}")
    fraction = float(value)
    if not 0.0 < fraction < 1.0:
        raise ValueError(f"Fraction must be between zero and one: {name}")
    return fraction


def _positive_integer(table: dict[str, object], name: str) -> int:
    value = table.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"Missing or invalid positive integer: {name}")
    return value


def _positive_float(table: dict[str, object], name: str) -> float:
    value = table.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0.0:
        raise ValueError(f"Missing or invalid positive number: {name}")
    return float(value)


def _boolean(table: dict[str, object], name: str) -> bool:
    value = table.get(name)
    if not isinstance(value, bool):
        raise ValueError(f"Missing or invalid boolean: {name}")
    return value


def _choice(table: dict[str, object], name: str, allowed: tuple[str, ...]) -> str:
    value = _string(table, name)
    if value not in allowed:
        raise ValueError(f"Value for {name} must be one of {allowed}")
    return value


def _load_baseline_config(table: dict[str, object]) -> BaselineConfig:
    ngram_min = _positive_integer(table, "ngram_min")
    ngram_max = _positive_integer(table, "ngram_max")
    if ngram_min > ngram_max:
        raise ValueError("Baseline ngram_min must not exceed ngram_max")

    class_weight = _choice(table, "class_weight", APPROVED_BASELINE_CLASS_WEIGHTS)
    return BaselineConfig(
        lowercase=_boolean(table, "lowercase"),
        ngram_min=ngram_min,
        ngram_max=ngram_max,
        max_features=_positive_integer(table, "max_features"),
        min_df=_positive_integer(table, "min_df"),
        sublinear_tf=_boolean(table, "sublinear_tf"),
        solver=_choice(table, "solver", APPROVED_BASELINE_SOLVERS),
        regularization_c=_positive_float(table, "regularization_c"),
        max_iter=_positive_integer(table, "max_iter"),
        class_weight=None if class_weight == "none" else class_weight,
    )


def load_foundation_config(path: Path) -> FoundationConfig:
    """Load and validate identifiers and status vocabulary without ML behavior."""

    with path.open("rb") as stream:
        document = tomllib.load(stream)

    project = _table(document, "project")
    data = _table(document, "data")
    baseline = _table(document, "baseline")
    model = _table(document, "model")
    paths = _table(document, "paths")
    status = _table(document, "status")

    seed = project.get("seed")
    allowed = status.get("allowed")
    if not isinstance(seed, int):
        raise ValueError("Missing or invalid integer: seed")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ValueError("Missing or invalid status vocabulary")

    vocabulary = tuple(allowed)
    if vocabulary != STATUS_VOCABULARY:
        raise ValueError("Status vocabulary does not match repository governance")

    dataset_id = _string(data, "dataset_id")
    dataset_revision = _string(data, "dataset_revision")
    if dataset_id != BANKING77_DATASET_ID:
        raise ValueError("Dataset identifier does not match the approved BANKING77 source")
    if dataset_revision != BANKING77_DATASET_REVISION:
        raise ValueError("Dataset revision does not match the approved immutable pin")

    return FoundationConfig(
        seed=seed,
        dataset_id=dataset_id,
        dataset_revision=dataset_revision,
        validation_fraction=_fraction(data, "validation_fraction"),
        data_root=Path(_string(paths, "data_root")),
        artifact_root=Path(_string(paths, "artifact_root")),
        report_root=Path(_string(paths, "report_root")),
        base_model_id=_string(model, "base_model_id"),
        base_model_revision=_string(model, "base_model_revision"),
        baseline=_load_baseline_config(baseline),
        status_vocabulary=vocabulary,
    )
