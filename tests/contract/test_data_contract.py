from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from datasets import (  # type: ignore[import-untyped]
    ClassLabel,
    Dataset,
    DatasetDict,
    Features,
    Value,
)

from intentguard.config import BANKING77_DATASET_REVISION, load_foundation_config
from intentguard.data import (
    CANONICAL_LABEL_MAP_SHA256,
    CANONICAL_LABEL_NAMES,
    LABEL_COUNT,
    DataContractError,
    prepare_dataset,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_SPLIT_FINGERPRINTS = {
    "train": "0f8b67c24d006cca95206d772cf385ea54c7de9e827c758b6f76775916c28e1c",
    "validation": "b50de7cd3b15e7dab510fa5d78a6efed8872f7fee76ed278029a7e27b4a67aa4",
    "test": "bb3573f0f18a1cf109cb490605e3df014e168a70d4681fc90677d008bc18af9a",
}


def _valid_source() -> DatasetDict:
    features = Features(
        {"text": Value("string"), "label": ClassLabel(names=CANONICAL_LABEL_NAMES)}
    )
    return DatasetDict(
        {
            "train": Dataset.from_dict(
                {
                    "text": [f"train {index}" for index in range(10_003)],
                    "label": [index % LABEL_COUNT for index in range(10_003)],
                },
                features=features,
            ),
            "test": Dataset.from_dict(
                {
                    "text": [f"test {index}" for index in range(3_080)],
                    "label": [index % LABEL_COUNT for index in range(3_080)],
                },
                features=features,
            ),
        }
    )


def test_data_contract_has_pinned_revision_and_expected_provenance(tmp_path: Path) -> None:
    config = replace(
        load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml"),
        data_root=tmp_path,
    )
    prepared = prepare_dataset(_valid_source(), config)

    assert prepared.provenance["source"] == {
        "dataset_id": "PolyAI/banking77",
        "dataset_revision": BANKING77_DATASET_REVISION,
        "license": "CC-BY-4.0",
        "license_reference": "https://creativecommons.org/licenses/by/4.0/",
    }
    assert prepared.provenance["source_split_counts"] == {"train": 10_003, "test": 3_080}
    assert prepared.provenance["derived_split_counts"] == {
        "train": 8_502,
        "validation": 1_501,
        "test": 3_080,
    }
    assert prepared.provenance["validation"] == {
        "fraction": 0.15,
        "seed": 42,
        "strategy": "StratifiedShuffleSplit",
        "source_split": "train",
    }
    assert prepared.label_names == CANONICAL_LABEL_NAMES
    assert prepared.provenance["label_names"] == list(CANONICAL_LABEL_NAMES)
    assert prepared.provenance["label_map_sha256"] == CANONICAL_LABEL_MAP_SHA256
    assert prepared.provenance["split_fingerprints"] == SYNTHETIC_SPLIT_FINGERPRINTS


def test_data_contract_rejects_source_split_count_drift(tmp_path: Path) -> None:
    source = _valid_source()
    source["test"] = source["test"].select(range(3_079))
    config = replace(
        load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml"),
        data_root=tmp_path,
    )

    with pytest.raises(DataContractError, match="10003 train and 3080 test"):
        prepare_dataset(source, config)
