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

from intentguard.config import FoundationConfig, load_foundation_config
from intentguard.data import (
    LABEL_COUNT,
    DataContractError,
    load_pinned_dataset,
    prepare_dataset,
    provenance_directory,
    write_provenance,
)
from intentguard.schemas import CanonicalExample, PreparedDataset

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _config(tmp_path: Path) -> FoundationConfig:
    return replace(
        load_foundation_config(REPOSITORY_ROOT / "configs" / "default.toml"),
        data_root=tmp_path,
    )


def _source_dataset(
    *, duplicate_test_text: bool = False, label_count: int = LABEL_COUNT
) -> DatasetDict:
    label_names = [f"intent_{index:02d}" for index in range(label_count)]
    features = Features(
        {
            "text": Value("string"),
            "label": ClassLabel(names=label_names),
        }
    )
    train_size = 10_003
    test_size = 3_080
    test_texts = [f"test text {index}" for index in range(test_size)]
    if duplicate_test_text:
        test_texts[1] = test_texts[0]
    return DatasetDict(
        {
            "train": Dataset.from_dict(
                {
                    "text": [f"train text {index}" for index in range(train_size)],
                    "label": [index % label_count for index in range(train_size)],
                },
                features=features,
            ),
            "test": Dataset.from_dict(
                {
                    "text": test_texts,
                    "label": [index % label_count for index in range(test_size)],
                },
                features=features,
            ),
        }
    )


def test_preparation_preserves_canonical_test_and_is_deterministic(tmp_path: Path) -> None:
    config = _config(tmp_path)
    source = _source_dataset(duplicate_test_text=True)

    first = prepare_dataset(source, config)
    second = prepare_dataset(source, config)

    assert len(first.train) == 8_502
    assert len(first.validation) == 1_501
    assert len(first.test) == 3_080
    assert all(example.example_id.startswith("train:") for example in first.train)
    assert all(example.example_id.startswith("train:") for example in first.validation)
    assert all(example.example_id.startswith("test:") for example in first.test)
    assert first.label_names == tuple(f"intent_{index:02d}" for index in range(LABEL_COUNT))
    assert first.provenance["split_fingerprints"] == second.provenance["split_fingerprints"]
    assert first.provenance["label_map_sha256"] == second.provenance["label_map_sha256"]
    duplicate_statistics = first.provenance["duplicate_text_statistics"]
    assert isinstance(duplicate_statistics, dict)
    per_split = duplicate_statistics["per_split"]
    assert isinstance(per_split, dict)
    test_statistics = per_split["test"]
    assert isinstance(test_statistics, dict)
    assert test_statistics["duplicate_examples"] == 1


def test_preparation_rejects_missing_text_column(tmp_path: Path) -> None:
    source = _source_dataset()
    source["train"] = source["train"].remove_columns("text")

    with pytest.raises(DataContractError, match="text and label"):
        prepare_dataset(source, _config(tmp_path))


def test_preparation_rejects_noncanonical_classlabel_mapping(tmp_path: Path) -> None:
    source = _source_dataset(label_count=LABEL_COUNT - 1)

    with pytest.raises(DataContractError, match="exactly 77 unique label names"):
        prepare_dataset(source, _config(tmp_path))


def test_prepared_validation_rejects_split_overlap() -> None:
    label_names = tuple(f"intent_{index:02d}" for index in range(LABEL_COUNT))
    example = CanonicalExample(
        example_id="train:000001",
        text="A valid request",
        label_id=0,
        label_name=label_names[0],
        split="train",
    )
    overlapping_test_example = replace(example, split="test")
    prepared = PreparedDataset(
        train=(example,),
        validation=(),
        test=(overlapping_test_example,),
        label_names=label_names,
        provenance={},
    )

    from intentguard.data import validate_prepared_dataset

    with pytest.raises(DataContractError, match="overlaps"):
        validate_prepared_dataset(prepared)


def test_pinned_loader_uses_configuration_and_writes_deterministic_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = _source_dataset()
    captured: dict[str, object] = {}

    def fake_load_dataset(*args: object, **kwargs: object) -> DatasetDict:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return source

    monkeypatch.setattr("intentguard.data.load_dataset", fake_load_dataset)
    config = _config(tmp_path)
    prepared = prepare_dataset(load_pinned_dataset(config), config)
    destination = write_provenance(prepared, provenance_directory(config))

    assert captured["args"] == (config.dataset_id,)
    assert captured["kwargs"] == {
        "revision": config.dataset_revision,
        "cache_dir": str(tmp_path / "cache"),
    }
    assert destination.read_text(encoding="utf-8").endswith("\n")
    assert destination.parent == tmp_path / f"banking77-{config.dataset_revision}"


def test_pinned_loader_wraps_cache_error_with_source_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _config(tmp_path)

    def unavailable_load_dataset(*args: object, **kwargs: object) -> DatasetDict:
        raise OSError("simulated offline dataset service")

    monkeypatch.setattr("intentguard.data.load_dataset", unavailable_load_dataset)

    with pytest.raises(DataContractError) as error:
        load_pinned_dataset(config)

    assert config.dataset_id in str(error.value)
    assert config.dataset_revision in str(error.value)
    assert "connect once" in str(error.value)
    assert "cache" in str(error.value)
    assert isinstance(error.value.__cause__, OSError)
