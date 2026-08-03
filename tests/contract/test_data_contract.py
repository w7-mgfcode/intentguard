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
from intentguard.data import LABEL_COUNT, DataContractError, prepare_dataset

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _valid_source() -> DatasetDict:
    label_names = [f"intent_{index:02d}" for index in range(LABEL_COUNT)]
    features = Features(
        {"text": Value("string"), "label": ClassLabel(names=label_names)}
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
    assert len(prepared.label_names) == LABEL_COUNT


def test_data_contract_rejects_source_split_count_drift(tmp_path: Path) -> None:
    source = _valid_source()
    source["test"] = source["test"].select(range(3_079))
    config = replace(
        load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml"),
        data_root=tmp_path,
    )

    with pytest.raises(DataContractError, match="10003 train and 3080 test"):
        prepare_dataset(source, config)
