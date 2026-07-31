"""Typed loading for repository-foundation configuration only."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

UNRESOLVED_REVISION: Final = "UNRESOLVED"
STATUS_VOCABULARY: Final = (
    "Implemented",
    "Measured",
    "Partial",
    "Mocked",
    "Blocked",
    "Planned",
)


@dataclass(frozen=True)
class FoundationConfig:
    """The small configuration subset Gate A is allowed to interpret."""

    seed: int
    dataset_id: str
    dataset_revision: str
    base_model_id: str
    base_model_revision: str
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


def load_foundation_config(path: Path) -> FoundationConfig:
    """Load and validate identifiers and status vocabulary without ML behavior."""

    with path.open("rb") as stream:
        document = tomllib.load(stream)

    project = _table(document, "project")
    data = _table(document, "data")
    model = _table(document, "model")
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

    return FoundationConfig(
        seed=seed,
        dataset_id=_string(data, "dataset_id"),
        dataset_revision=_string(data, "dataset_revision"),
        base_model_id=_string(model, "base_model_id"),
        base_model_revision=_string(model, "base_model_revision"),
        status_vocabulary=vocabulary,
    )
