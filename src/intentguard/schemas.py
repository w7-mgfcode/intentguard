"""Typed data-contract records for the pinned BANKING77 dataset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SplitName = Literal["train", "validation", "test"]


@dataclass(frozen=True, slots=True)
class CanonicalExample:
    """One validated example with a stable upstream-derived identity."""

    example_id: str
    text: str
    label_id: int
    label_name: str
    split: SplitName


@dataclass(frozen=True, slots=True)
class PreparedDataset:
    """Validated canonical splits and deterministic provenance."""

    train: tuple[CanonicalExample, ...]
    validation: tuple[CanonicalExample, ...]
    test: tuple[CanonicalExample, ...]
    label_names: tuple[str, ...]
    provenance: dict[str, object]
