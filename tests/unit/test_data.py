from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

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
    CANONICAL_LABEL_NAMES,
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
    *, duplicate_test_text: bool = False, label_names: tuple[str, ...] = CANONICAL_LABEL_NAMES
) -> DatasetDict:
    label_count = len(label_names)
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
    assert first.label_names == CANONICAL_LABEL_NAMES
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
    source = _source_dataset(label_names=CANONICAL_LABEL_NAMES[:-1])

    with pytest.raises(DataContractError, match="exactly 77 unique label names"):
        prepare_dataset(source, _config(tmp_path))


@pytest.mark.parametrize(
    "label_names",
    [
        CANONICAL_LABEL_NAMES[1:2] + CANONICAL_LABEL_NAMES[0:1] + CANONICAL_LABEL_NAMES[2:],
        ("renamed_intent", *CANONICAL_LABEL_NAMES[1:]),
    ],
)
def test_preparation_rejects_reordered_or_renamed_classlabel_mapping(
    tmp_path: Path, label_names: tuple[str, ...]
) -> None:
    with pytest.raises(DataContractError, match="approved canonical order"):
        prepare_dataset(_source_dataset(label_names=label_names), _config(tmp_path))


def test_prepared_validation_rejects_split_overlap() -> None:
    example = CanonicalExample(
        example_id="train:000001",
        text="A valid request",
        label_id=0,
        label_name=CANONICAL_LABEL_NAMES[0],
        split="train",
    )
    overlapping_test_example = replace(example, split="test")
    prepared = PreparedDataset(
        train=(example,),
        validation=(),
        test=(overlapping_test_example,),
        label_names=CANONICAL_LABEL_NAMES,
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


def test_pinned_loader_rejects_non_datasetdict_with_source_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = _config(tmp_path)

    def invalid_load_dataset(*args: object, **kwargs: object) -> object:
        return {"train": "not a DatasetDict"}

    monkeypatch.setattr("intentguard.data.load_dataset", invalid_load_dataset)

    with pytest.raises(DataContractError, match="DatasetDict") as error:
        load_pinned_dataset(config)

    assert config.dataset_id in str(error.value)
    assert config.dataset_revision in str(error.value)


def test_write_provenance_uses_unique_atomic_temp_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = prepare_dataset(_source_dataset(), _config(tmp_path))
    output_directory = tmp_path / "concurrent-provenance"
    barrier = Barrier(2)
    original_replace = Path.replace

    def synchronized_replace(source: Path, destination: Path) -> Path:
        if source.parent == output_directory and source.name.startswith("provenance"):
            barrier.wait(timeout=5)
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", synchronized_replace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        destinations = list(
            executor.map(lambda _: write_provenance(prepared, output_directory), range(2))
        )

    assert destinations == [output_directory / "provenance.json"] * 2
    assert json.loads((output_directory / "provenance.json").read_text(encoding="utf-8")) == (
        prepared.provenance
    )
    assert list(output_directory.glob("*.tmp")) == []


def test_write_provenance_cleans_its_temp_file_after_replace_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prepared = prepare_dataset(_source_dataset(), _config(tmp_path))
    output_directory = tmp_path / "failed-provenance"

    def failing_replace(source: Path, destination: Path) -> Path:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", failing_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_provenance(prepared, output_directory)

    assert list(output_directory.glob("*.tmp")) == []
